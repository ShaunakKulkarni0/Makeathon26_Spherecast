from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ..services.orchestrator import load_requirements_defaults


router = APIRouter()

_ROOT = Path(__file__).resolve().parents[4]
_DB_PATH = _ROOT / "db.sqlite"
_SCORING_CSV = _ROOT / "data" / "scoring_capsuline_materials.csv"
_COMPOUND_GROUPS_CSV = _ROOT / "compound_groups.csv"


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
    return " ".join(cleaned.split())


def _humanize_name(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.replace("|", " ").split())


def _infer_capsule_group(name: str, material_id: str) -> str:
    text = f"{name} {material_id}".lower()
    if "pet" in text:
        return "Pet Capsules"
    if "pullulan" in text:
        return "Pullulan Capsules"
    if "enteric" in text or "acid resistant" in text:
        return "Enteric Capsules"
    if "colored" in text or "colour" in text or "color" in text:
        return "Colored Capsules"
    if "vegetarian" in text or "vegan" in text:
        return "Vegetarian Capsules"
    if "gelatin" in text or "gelatine" in text:
        return "Gelatin Capsules"
    return "Scoring Catalog"


def _load_compound_groups() -> dict[int, str]:
    if not _COMPOUND_GROUPS_CSV.exists():
        return {}

    mapping: dict[int, str] = {}
    with _COMPOUND_GROUPS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_id = (row.get("product_id") or "").strip()
            if not raw_id.isdigit():
                continue
            group_name = (row.get("group_name") or "").strip()
            if group_name:
                mapping[int(raw_id)] = group_name
    return mapping


def _load_scoring_materials() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not _SCORING_CSV.exists():
        raise HTTPException(status_code=500, detail=f"Missing scoring CSV: {_SCORING_CSV}")

    scoring_materials: list[dict[str, Any]] = []
    by_normalized_name: dict[str, dict[str, Any]] = {}
    with _SCORING_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            scoring_id = (row.get("id") or "").strip()
            scoring_name = (row.get("name") or "").strip()
            if not scoring_id:
                continue

            normalized_name = _normalize_text(scoring_name)
            entry = {
                "id": f"score-{scoring_id}",
                "name": scoring_name,
                "sku": None,
                "supplier_name": "Capsuline",
                "group": _infer_capsule_group(scoring_name, scoring_id),
                "has_data": True,
                "score_material_id": scoring_id,
                "source": "scoring_csv",
                "_normalized_name": normalized_name,
            }
            scoring_materials.append(entry)
            if normalized_name and normalized_name not in by_normalized_name:
                by_normalized_name[normalized_name] = entry

    return scoring_materials, by_normalized_name


def _load_sqlite_materials(
    compound_groups: dict[int, str],
    scoring_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Missing SQLite DB: {_DB_PATH}")

    materials: list[dict[str, Any]] = []
    with sqlite3.connect(_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT p.Id, p.SKU, p.canonical_string, p.sku_category, p.Type, c.Name
            FROM Product p
            LEFT JOIN Company c ON c.Id = p.CompanyId
            """
        ).fetchall()

    for product_id, sku, canonical_string, sku_category, product_type, company_name in rows:
        readable_name = _humanize_name(canonical_string or sku or "")
        normalized_name = _normalize_text(readable_name)
        matched_scoring = scoring_by_name.get(normalized_name)
        has_data = matched_scoring is not None

        materials.append(
            {
                "id": f"db-{product_id}",
                "name": readable_name or f"Product {product_id}",
                "sku": sku,
                "supplier_name": (company_name or "").strip() or "Unknown Supplier",
                "product_type": product_type,
                "group": (
                    compound_groups.get(product_id)
                    or (sku_category or "").strip()
                    or "Ungrouped"
                ),
                "has_data": has_data,
                "score_material_id": matched_scoring["score_material_id"] if has_data else None,
                "source": "sqlite",
                "_normalized_name": normalized_name,
            }
        )
    return materials


@router.get("/config")
def get_material_config() -> dict[str, Any]:
    compound_groups = _load_compound_groups()
    scoring_materials, scoring_by_name = _load_scoring_materials()
    sqlite_materials = _load_sqlite_materials(compound_groups, scoring_by_name)

    existing_names = {m["_normalized_name"] for m in sqlite_materials if m["_normalized_name"]}
    scoring_only = [
        m for m in scoring_materials if m["_normalized_name"] and m["_normalized_name"] not in existing_names
    ]

    materials = sqlite_materials + scoring_only
    materials.sort(key=lambda item: (0 if item["has_data"] else 1, item["name"].lower()))
    for material in materials:
        material.pop("_normalized_name", None)

    groups = sorted({(m.get("group") or "Ungrouped").strip() for m in materials})
    return {
        "materials": materials,
        "filters": {
            "groups": groups,
            "data_availability": [
                {"value": "all", "label": "All"},
                {"value": "has_data", "label": "With Data"},
                {"value": "no_data", "label": "Without Data"},
            ],
        },
        "requirements_defaults": load_requirements_defaults(),
    }
