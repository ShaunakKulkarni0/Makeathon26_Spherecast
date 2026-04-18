from __future__ import annotations

import csv
import json
from pathlib import Path

from shared.schemas import (
    CrawledMaterial,
    LeadTimeInfo,
    MaterialProperty,
    PriceInfo,
    QualityInfo,
    UserRequirements,
)


_REQUIREMENTS_REQUIRED_KEYS = (
    "destination_country",
    "critical_certs_json",
    "max_lead_time_days",
    "max_price_multiplier",
)
_REQUIREMENTS_QUANTITY_KEYS = ("max_quantity", "max_moq", "mqo")


def _parse_float(value: str | None, default: float | None = None) -> float | None:
    if value is None or value.strip() == "":
        return default
    return float(value)


def _parse_int(value: str | None, default: int | None = None) -> int | None:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _parse_bool(value: str | None, default: bool | None = None) -> bool | None:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return default


def _parse_json(value: str | None, fallback: object) -> object:
    if value is None or value.strip() == "":
        return fallback
    return json.loads(value)


def _is_non_empty(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _validate_requirements_row(row: dict[str, str], path: Path) -> None:
    if None in row and row[None]:
        raise ValueError(
            f"Ungueltige Requirements-CSV {path}: Zeile hat mehr Werte als Header-Spalten. "
            "Bitte Header und Spaltenreihenfolge pruefen."
        )

    missing_required = [key for key in _REQUIREMENTS_REQUIRED_KEYS if key not in row]
    if missing_required:
        raise ValueError(
            f"Ungueltige Requirements-CSV {path}: Fehlende Pflichtspalten: {', '.join(missing_required)}"
        )

    if not any(key in row for key in _REQUIREMENTS_QUANTITY_KEYS):
        raise ValueError(
            f"Ungueltige Requirements-CSV {path}: Mengen-Spalte fehlt. "
            "Erwartet eine von: max_quantity, max_moq, mqo."
        )


def _parse_max_quantity(row: dict[str, str], path: Path) -> int | None:
    values_by_key: dict[str, int] = {}
    for key in _REQUIREMENTS_QUANTITY_KEYS:
        raw = row.get(key)
        if not _is_non_empty(raw):
            continue
        try:
            parsed = _parse_int(raw)
        except ValueError as exc:
            raise ValueError(
                f"Ungueltiger Integer-Wert in Requirements-CSV {path}: Feld '{key}' = {raw!r}"
            ) from exc
        if parsed is not None:
            values_by_key[key] = parsed

    if not values_by_key:
        return None

    source_key = next(key for key in _REQUIREMENTS_QUANTITY_KEYS if key in values_by_key)
    canonical_value = values_by_key[source_key]
    conflicting = {
        key: value for key, value in values_by_key.items() if value != canonical_value
    }
    if conflicting:
        conflict_parts = ", ".join(f"{k}={v}" for k, v in sorted(values_by_key.items()))
        raise ValueError(
            f"Konflikt in Requirements-CSV {path}: Mengen-Spalten enthalten unterschiedliche Werte "
            f"({conflict_parts})."
        )

    return canonical_value


def _parse_properties(raw: str) -> dict[str, MaterialProperty]:
    parsed = _parse_json(raw, {})
    props: dict[str, MaterialProperty] = {}
    for key, data in parsed.items():
        props[key] = MaterialProperty(
            value=float(data["value"]),
            unit=str(data["unit"]),
        )
    return props


def _parse_quality(row: dict[str, str]) -> QualityInfo:
    supplier_rating = None
    rating_value = _parse_float(row.get("supplier_rating_value"))
    if rating_value is not None:
        supplier_rating = {
            "value": rating_value,
            "review_count": int(_parse_int(row.get("supplier_rating_reviews"), 0) or 0),
        }

    defect_rate = None
    defect_value = _parse_float(row.get("defect_rate_value"))
    if defect_value is not None:
        defect_rate = {
            "value": defect_value,
            "sample_size": int(_parse_int(row.get("defect_rate_sample"), 0) or 0),
        }

    on_time_delivery = None
    otd_value = _parse_float(row.get("on_time_delivery_value"))
    if otd_value is not None:
        on_time_delivery = {
            "value": otd_value,
            "sample_size": int(_parse_int(row.get("on_time_delivery_sample"), 0) or 0),
        }

    audit_score = None
    audit_value = _parse_float(row.get("audit_score_value"))
    if audit_value is not None:
        audit_score = {
            "value": audit_value,
            "age_months": int(_parse_int(row.get("audit_age_months"), 0) or 0),
            "passed": bool(_parse_bool(row.get("audit_passed"), False)),
        }

    return QualityInfo(
        supplier_rating=supplier_rating,
        defect_rate=defect_rate,
        on_time_delivery=on_time_delivery,
        years_in_business=_parse_int(row.get("years_in_business")),
        audit_score=audit_score,
    )


def material_from_row(row: dict[str, str]) -> CrawledMaterial:
    certifications = _parse_json(row.get("certifications_json"), [])
    tiers = _parse_json(row.get("price_tiers_json"), None)

    return CrawledMaterial(
        id=row["id"],
        name=row["name"],
        properties=_parse_properties(row["properties_json"]),
        certifications=list(certifications),
        price=PriceInfo(
            value=float(row["price_value"]),
            unit=row["price_unit"],
            tiers=tiers,  # type: ignore[arg-type]
        ),
        lead_time=LeadTimeInfo(
            days=int(row["lead_days"]),
            reliability=float(row["lead_reliability"]),
            type=row["lead_type"],
        ),
        quality=_parse_quality(row),
        moq=int(row["moq"]),
        country_of_origin=row["country_of_origin"],
        incoterm=row["incoterm"],
        source_url=row.get("source_url") or None,
    )


def load_materials_csv(path: Path) -> tuple[CrawledMaterial, list[CrawledMaterial]]:
    original: CrawledMaterial | None = None
    candidates: list[CrawledMaterial] = []

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = row["role"].strip().upper()
            material = material_from_row(row)
            if role == "ORIGINAL":
                original = material
            elif role == "CANDIDATE":
                candidates.append(material)
            else:
                raise ValueError(f"Unbekannte role '{role}' in {path}")

    if original is None:
        raise ValueError(f"Keine ORIGINAL-Zeile in {path}")

    return original, candidates


def load_requirements_csv(path: Path) -> UserRequirements:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Leere Requirements-CSV: {path}")

    row = rows[0]
    _validate_requirements_row(row, path)
    critical_certs = _parse_json(row.get("critical_certs_json"), None)
    max_quantity = _parse_max_quantity(row, path)

    return UserRequirements(
        max_quantity=max_quantity,
        destination_country=row.get("destination_country") or "DE",
        critical_certs=critical_certs,  # type: ignore[arg-type]
        max_lead_time_days=_parse_int(row.get("max_lead_time_days")),
        max_price_multiplier=float(row.get("max_price_multiplier") or "2.0"),
    )
