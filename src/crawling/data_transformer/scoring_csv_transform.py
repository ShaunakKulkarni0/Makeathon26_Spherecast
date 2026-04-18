from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse


INPUT_FIELDS = (
    "product_name",
    "price",
    "supplier",
    "properties",
    "certifications",
    "lead_days",
    "lead_type",
    "years_in_business",
    "source_url",
)

OUTPUT_FIELDS = (
    "role",
    "id",
    "name",
    "properties_json",
    "certifications_json",
    "price_value",
    "price_unit",
    "price_tiers_json",
    "lead_days",
    "lead_reliability",
    "lead_type",
    "supplier_rating_value",
    "supplier_rating_reviews",
    "defect_rate_value",
    "defect_rate_sample",
    "on_time_delivery_value",
    "on_time_delivery_sample",
    "years_in_business",
    "audit_score_value",
    "audit_age_months",
    "audit_passed",
    "moq",
    "country_of_origin",
    "incoterm",
    "source_url",
)

NUMERIC_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _normalize_unknown(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.strip()
    if not normalized or normalized.upper() == "NONE":
        return ""
    return normalized


def _parse_float(value: str | None, default: float) -> float:
    cleaned = _normalize_unknown(value)
    if not cleaned:
        return default

    direct = cleaned.replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(direct)
    except ValueError:
        match = NUMERIC_PATTERN.search(cleaned)
        if not match:
            return default
        return float(match.group(0).replace(",", "."))


def _parse_int(value: str | None) -> int | None:
    cleaned = _normalize_unknown(value)
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        match = NUMERIC_PATTERN.search(cleaned)
        if not match:
            return None
        return int(float(match.group(0).replace(",", ".")))


def _parse_certifications(raw: str | None) -> list[str]:
    cleaned = _normalize_unknown(raw)
    if not cleaned:
        return []
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return []


def _normalize_lead_type(value: str | None) -> str:
    cleaned = _normalize_unknown(value).lower()
    if cleaned in {"stock", "in stock", "instock"}:
        return "stock"
    if cleaned == "express":
        return "express"
    if cleaned == "standard":
        return "standard"
    return "unknown"


def _slug_from_url(url: str | None, row_index: int) -> str:
    cleaned = _normalize_unknown(url)
    if cleaned:
        try:
            parsed = urlparse(cleaned)
            candidate = parsed.path.rstrip("/").split("/")[-1]
            slug = re.sub(r"[^a-zA-Z0-9-]+", "-", candidate).strip("-").lower()
            if slug:
                return slug
        except Exception:
            pass
    return f"capsuline-{row_index:03d}"


def _extract_numeric_properties(raw: str | None) -> dict[str, dict[str, float | str]]:
    cleaned = _normalize_unknown(raw)
    if not cleaned:
        return {}

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}

    extracted: dict[str, dict[str, float | str]] = {}

    def walk(value: object, prefix: str) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                part = str(key).strip()
                if not part:
                    continue
                next_prefix = f"{prefix}.{part}" if prefix else part
                walk(nested, next_prefix)
            return
        if isinstance(value, list):
            for idx, nested in enumerate(value):
                next_prefix = f"{prefix}.{idx}" if prefix else str(idx)
                walk(nested, next_prefix)
            return
        if isinstance(value, (int, float)):
            if prefix:
                extracted[prefix] = {"value": float(value), "unit": "unknown"}
            return
        if isinstance(value, str):
            match = NUMERIC_PATTERN.search(value)
            if not match or not prefix:
                return
            extracted[prefix] = {
                "value": float(match.group(0).replace(",", ".")),
                "unit": "unknown",
            }

    walk(parsed, "")
    return extracted


def _validate_input_header(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Input CSV has no header.")

    missing = [field for field in INPUT_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(
            f"Input CSV missing required fields: {', '.join(missing)}"
        )


def _build_output_row(
    row: dict[str, str],
    index: int,
    original_id: str | None,
) -> dict[str, str]:
    source_url = _normalize_unknown(row.get("source_url"))
    row_id = _slug_from_url(source_url, index)

    role = "CANDIDATE"
    if original_id:
        role = "ORIGINAL" if row_id == original_id else "CANDIDATE"
    elif index == 1:
        role = "ORIGINAL"

    properties_json = json.dumps(_extract_numeric_properties(row.get("properties")))
    certifications_json = json.dumps(_parse_certifications(row.get("certifications")))
    years_in_business = _parse_int(row.get("years_in_business"))
    lead_days = _parse_int(row.get("lead_days")) or 30

    return {
        "role": role,
        "id": row_id,
        "name": _normalize_unknown(row.get("product_name")) or row_id,
        "properties_json": properties_json,
        "certifications_json": certifications_json,
        "price_value": f"{_parse_float(row.get('price'), default=0.0):.6f}".rstrip("0").rstrip(".") or "0",
        "price_unit": "EUR/unit",
        "price_tiers_json": "",
        "lead_days": str(lead_days),
        "lead_reliability": "0.5",
        "lead_type": _normalize_lead_type(row.get("lead_type")),
        "supplier_rating_value": "",
        "supplier_rating_reviews": "",
        "defect_rate_value": "",
        "defect_rate_sample": "",
        "on_time_delivery_value": "",
        "on_time_delivery_sample": "",
        "years_in_business": "" if years_in_business is None else str(years_in_business),
        "audit_score_value": "",
        "audit_age_months": "",
        "audit_passed": "",
        "moq": "1",
        "country_of_origin": "UNKNOWN",
        "incoterm": "EXW",
        "source_url": source_url,
    }


def transform_extracted_to_scoring_csv(
    input_path: Path,
    output_path: Path,
    original_id: str | None = None,
) -> tuple[int, int]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    numeric_properties_total = 0
    output_rows: list[dict[str, str]] = []

    with input_path.open(newline="", encoding="utf-8") as in_file:
        reader = csv.DictReader(in_file)
        _validate_input_header(reader.fieldnames)

        for idx, row in enumerate(reader, start=1):
            out_row = _build_output_row(row, idx, original_id=original_id)
            total_rows += 1
            props = json.loads(out_row["properties_json"])
            numeric_properties_total += len(props)
            output_rows.append(out_row)

    if total_rows == 0:
        raise ValueError("Input CSV is empty.")

    if original_id and not any(row["role"] == "ORIGINAL" for row in output_rows):
        output_rows[0]["role"] = "ORIGINAL"

    with output_path.open("w", newline="", encoding="utf-8") as out_file:
        writer = csv.DictWriter(out_file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    return total_rows, numeric_properties_total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform extracted Capsuline CSV into scoring-compatible CSV."
    )
    parser.add_argument(
        "--input",
        default="data/extracted_capsuline_products.csv",
        help="Input extracted CSV path.",
    )
    parser.add_argument(
        "--output",
        default="data/scoring_capsuline_materials.csv",
        help="Output scoring CSV path.",
    )
    parser.add_argument(
        "--original-id",
        default=None,
        help="Optional id to mark as ORIGINAL. Otherwise first row is ORIGINAL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    total, numeric_props = transform_extracted_to_scoring_csv(
        input_path=Path(args.input),
        output_path=Path(args.output),
        original_id=args.original_id,
    )
    print(
        f"Transformed {total} rows to scoring CSV at {args.output}. "
        f"Extracted {numeric_props} numeric properties."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
