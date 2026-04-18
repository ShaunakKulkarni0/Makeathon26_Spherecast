from __future__ import annotations

import csv
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from shared.schemas import UserRequirements
from src.scoring.pipeline import find_substitutes
from tests.scoring.csv_loader import load_requirements_csv, material_from_row


_ROOT = Path(__file__).resolve().parents[4]
_MATERIALS_CSV = _ROOT / "tests" / "scoring" / "data" / "gesamt_materials.csv"
_REQUIREMENTS_CSV = _ROOT / "tests" / "scoring" / "data" / "gesamt_requirements.csv"


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, tuple):
        return [_serialize(v) for v in value]
    return value


def _load_material_rows() -> list[dict[str, str]]:
    if not _MATERIALS_CSV.exists():
        raise HTTPException(status_code=500, detail=f"Missing CSV: {_MATERIALS_CSV}")

    with _MATERIALS_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise HTTPException(status_code=500, detail="Materials CSV is empty.")
    return rows


def list_csv_materials() -> list[dict[str, str]]:
    rows = _load_material_rows()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "role": row.get("role", "").upper(),
            "label": f"{row['name']} ({row['id']})",
        }
        for row in rows
    ]


def load_requirements_defaults() -> dict[str, Any]:
    try:
        requirements = load_requirements_csv(_REQUIREMENTS_CSV)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load requirements CSV: {exc}") from exc
    return _serialize(requirements)


def _merge_requirements(
    base: UserRequirements,
    override: dict[str, Any] | None = None,
) -> UserRequirements:
    if not override:
        return base

    merged = UserRequirements(
        max_quantity=base.max_quantity,
        destination_country=base.destination_country,
        critical_certs=list(base.critical_certs) if base.critical_certs else None,
        max_lead_time_days=base.max_lead_time_days,
        max_price_multiplier=base.max_price_multiplier,
    )

    if "max_quantity" in override:
        merged.max_quantity = override["max_quantity"]
    if "destination_country" in override:
        merged.destination_country = override["destination_country"] or "DE"
    if "critical_certs" in override:
        critical = override["critical_certs"]
        merged.critical_certs = list(critical) if critical else None
    if "max_lead_time_days" in override:
        merged.max_lead_time_days = override["max_lead_time_days"]
    if "max_price_multiplier" in override:
        merged.max_price_multiplier = float(override["max_price_multiplier"] or 2.0)

    return merged


def _build_temp_scoring_csv(selected_material_id: str, rows: list[dict[str, str]]) -> Path:
    row_by_id = {row["id"]: row for row in rows}
    if selected_material_id not in row_by_id:
        raise HTTPException(status_code=404, detail=f"Material id '{selected_material_id}' not found in CSV.")

    ordered_rows: list[dict[str, str]] = []
    selected_row = dict(row_by_id[selected_material_id])
    selected_row["role"] = "ORIGINAL"
    ordered_rows.append(selected_row)

    for row in rows:
        if row["id"] == selected_material_id:
            continue
        candidate_row = dict(row)
        candidate_row["role"] = "CANDIDATE"
        ordered_rows.append(candidate_row)

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        prefix="ui_scoring_",
        delete=False,
        newline="",
        encoding="utf-8",
    )
    temp_path = Path(temp_file.name)
    temp_file.close()

    fieldnames = list(rows[0].keys())
    if "role" not in fieldnames:
        fieldnames = ["role"] + fieldnames

    with temp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in ordered_rows:
            writer.writerow(row)

    return temp_path


def run_csv_scoring(
    selected_material_id: str,
    weights: dict[str, float] | None = None,
    top_n: int = 3,
    requirements_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = _load_material_rows()
    temp_csv_path = _build_temp_scoring_csv(selected_material_id, rows)

    try:
        with temp_csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            temp_rows = list(reader)

        if not temp_rows:
            raise HTTPException(status_code=500, detail="Temporary scoring CSV is empty.")

        original = material_from_row(temp_rows[0])
        candidates = [material_from_row(row) for row in temp_rows[1:]]
        requirements_default = load_requirements_csv(_REQUIREMENTS_CSV)
        requirements = _merge_requirements(requirements_default, requirements_override)

        result = find_substitutes(
            original=original,
            candidates=candidates,
            user_requirements=requirements,
            weights=weights,
            top_n=top_n,
        )
        payload = _serialize(result)
        payload.setdefault("metadata", {})
        payload["metadata"]["selected_material_id"] = selected_material_id
        payload["metadata"]["requirements"] = _serialize(requirements)
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}") from exc
    finally:
        try:
            temp_csv_path.unlink(missing_ok=True)
        except Exception:
            pass
