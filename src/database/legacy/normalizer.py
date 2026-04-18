# Data Layer/normalizer.py

from __future__ import annotations
import json
import logging
from typing import Optional
from src.database.legacy.shared.openai_client import chat_completion
from shared.schemas import NormalizationResult, ExtractedEntities, SKUCategory
from shared.constants import NORMALIZATION_MODEL
from src.database.legacy.prompt_builder import build_normalization_prompt
from src.database.legacy.schema_discovery import load_schema

logger = logging.getLogger(__name__)


def _get_system_prompt(schema: dict | None) -> str:
    """
    Nimmt das Schema direkt entgegen (nicht conn),
    damit wir es nicht bei jedem Call neu laden.
    """
    return build_normalization_prompt(schema)


def normalize_sku(
    sku_name: str,
    sku_id: int | None = None,
    model: str = NORMALIZATION_MODEL,
    schema: dict | None = None,   # ← Schema statt conn
) -> NormalizationResult:

    system_prompt = _get_system_prompt(schema)

    raw_text = chat_completion(
        model=model,
        system_prompt=system_prompt,
        user_content=sku_name,
        json_mode=True,
        temperature=0.0,
    )

    result = _parse_normalization_response(raw_text, sku_name)
    result.sku_id = sku_id
    result.sku_name = sku_name
    return result


def normalize_sku_batch(
    skus: list[tuple[int, str]],
    model: str = NORMALIZATION_MODEL,
    schema: dict | None = None,   # ← Schema einmal rein, für alle SKUs
) -> list[NormalizationResult]:

    results: list[NormalizationResult] = []
    for sku_id, sku_name in skus:
        try:
            result = normalize_sku(
                sku_name,
                sku_id=sku_id,
                model=model,
                schema=schema,    # ← weitergeben
            )
            results.append(result)
        except Exception as exc:
            logger.error(
                "Normalization failed for sku_id=%s (%r): %s",
                sku_id, sku_name, exc,
            )
    return results


def _parse_normalization_response(raw_text: str, sku_name: str) -> NormalizationResult:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(inner).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON for SKU {sku_name!r}. "
            f"Raw response: {raw_text[:500]}"
        ) from exc

    try:
        entities_data = data.get("extracted_entities", {})
        entities = ExtractedEntities(
            cas_number=entities_data.get("cas_number"),
            dosage_or_concentration=entities_data.get("dosage_or_concentration"),
            chiral_form=entities_data.get("chiral_form"),
        )
        result = NormalizationResult(
            category=SKUCategory(data["category"]),
            extracted_entities=entities,
            canonical_string=data["canonical_string"],
        )
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"LLM response failed schema validation for SKU {sku_name!r}: {exc}. "
            f"Parsed data: {data}"
        ) from exc

    _validate_business_rules(result, sku_name)
    return result


def _validate_business_rules(result: NormalizationResult, sku_name: str) -> None:
    """
    Nur noch generische Regeln — keine hardcodierten Domain-Strings.
    """
    cs = result.canonical_string

    if not cs or len(cs.strip()) < 5:
        logger.warning(
            "SKU %r: canonical_string is suspiciously short: %r",
            sku_name, cs,
        )

    if result.category == SKUCategory.BRANDED:
        if "Substitution" not in cs:
            logger.warning(
                "Branded SKU %r: canonical_string missing substitution note.",
                sku_name,
            )

    if result.category == SKUCategory.CHEMICAL:
        if result.extracted_entities.cas_number is None:
            logger.warning(
                "Chemical SKU %r: CAS number could not be extracted.",
                sku_name,
            )