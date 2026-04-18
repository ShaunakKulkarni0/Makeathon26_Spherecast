"""
Data Layer/normalizer.py

Layer 1, step 1.1 — LLM normalization.

Responsibilities:
  - Build the system prompt for the normalization LLM call.
  - Send the raw SKU name to the OpenAI Chat API (via shared/openai_client.py).
  - Parse and validate the JSON response into a NormalizationResult.
  - Return the result to the caller (layer1_pipeline.py handles DB persistence).

The prompt instructs the model to output strict JSON — no prose preamble,
no markdown fences, just the schema defined in shared/schemas.py.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from shared.openai_client import chat_completion
from shared.schemas import NormalizationResult, ExtractedEntities, SKUCategory
from shared.constants import NORMALIZATION_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
# IMPORTANT: The phrase "JSON" must appear in the system prompt when
# response_format=json_object is used, otherwise OpenAI returns HTTP 400.
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an expert chemical and supply chain data normalizer.
Your task is to analyze a raw material/SKU name, classify it into one of 7 \
categories, and generate a "Canonical Description String".

Categories:
1. Chemical    (has CAS/IUPAC number)
2. Botanical   (plant-derived, extracts)
3. Bioactive   (probiotics, enzymes — metric is CFU or activity units like GDU)
4. Branded     (proprietary ingredients, e.g. "Albion TRAACS")
5. Excipient   (fillers, capsules, coatings)
6. Flavor/Color (E-numbers, FEMA)
7. Blend/Premix (mixture of multiple ingredients)

RULES FOR THE CANONICAL STRING:
- It MUST be a continuous natural language paragraph. DO NOT output a JSON \
stringified object inside this field.
- HARD EXTRACTION: You MUST explicitly state any numbers, dosages (mg, %), \
and chiral forms (L- vs. D-) present in the SKU name.
- If Chemical: include CAS number, molecular formula, form (salt/chelate/oxide), \
and general bioavailability context.
- If Branded: the string MUST contain the exact phrase \
"Substitution: never without license".
- If Bioactive: explicitly state the strain or activity unit in the string.

You MUST respond with ONLY valid JSON that matches this exact schema — \
no markdown fences, no preamble, no commentary:
{
  "category": "<Chemical|Botanical|Bioactive|Branded|Excipient|Flavor/Color|Blend/Premix|Unknown>",
  "extracted_entities": {
    "cas_number": "<string or null>",
    "dosage_or_concentration": "<string or null>",
    "chiral_form": "<string or null>"
  },
  "canonical_string": "<The generated continuous text paragraph.>"
}
"""


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def normalize_sku(
    sku_name: str,
    sku_id: Optional[int] = None,
    model: str = NORMALIZATION_MODEL,
) -> NormalizationResult:
    """
    Normalize a single raw SKU name into a structured NormalizationResult.

    Args:
        sku_name: The raw SKU string from the database (e.g. "Mag Cit 200mg").
        sku_id:   Optional database ID to attach to the result for traceability.
        model:    OpenAI model to use. Defaults to NORMALIZATION_MODEL constant.

    Returns:
        A validated NormalizationResult instance.

    Raises:
        ValueError: If the LLM returns malformed JSON or fails schema validation.
        openai_client.OpenAIError: On unrecoverable API errors.
    """
    logger.info("Normalizing SKU %s: %r", sku_id, sku_name)

    raw_text = chat_completion(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        user_content=sku_name,
        json_mode=True,
        temperature=0.0,
    )

    result = _parse_normalization_response(raw_text, sku_name)
    result.sku_id   = sku_id
    result.sku_name = sku_name
    return result


def normalize_sku_batch(
    skus: list[tuple[int, str]],
    model: str = NORMALIZATION_MODEL,
) -> list[NormalizationResult]:
    """
    Normalize a batch of (sku_id, sku_name) pairs sequentially.

    Note: OpenAI's Chat Completions endpoint does not support true batching
    for json_object mode, so calls are made one at a time. For throughput,
    consider wrapping this in asyncio or a thread pool at the caller level.

    Args:
        skus:  List of (sku_id, sku_name) tuples.
        model: OpenAI model to use.

    Returns:
        List of NormalizationResult objects in the same order as `skus`.
        Failed items are logged and skipped (None values are not included).
    """
    results: list[NormalizationResult] = []
    for sku_id, sku_name in skus:
        try:
            result = normalize_sku(sku_name, sku_id=sku_id, model=model)
            results.append(result)
        except Exception as exc:
            logger.error(
                "Normalization failed for sku_id=%s (%r): %s",
                sku_id, sku_name, exc,
            )
    return results


# ---------------------------------------------------------------------------
# Internal parsing
# ---------------------------------------------------------------------------

def _parse_normalization_response(raw_text: str, sku_name: str) -> NormalizationResult:
    """
    Parse the raw LLM text response into a NormalizationResult.
    Strips accidental markdown fences the model may still emit.

    Raises:
        ValueError: If JSON is invalid or fails Pydantic validation.
    """
    # Strip markdown fences that a misconfigured model might still emit
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first and last fence lines
        inner = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(inner).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON for SKU {sku_name!r}. "
            f"Raw response: {raw_text[:500]}"
        ) from exc

    # Pydantic validates enum membership and required fields
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
    Enforce domain rules that the LLM may occasionally violate.
    Logs warnings rather than raising — the pipeline continues with a flag.
    """
    cs = result.canonical_string

    if result.category == SKUCategory.BRANDED:
        if "Substitution: never without license" not in cs:
            logger.warning(
                "Branded SKU %r: canonical_string missing required substitution "
                "disclaimer. The LLM did not follow instructions.",
                sku_name,
            )

    if result.category == SKUCategory.CHEMICAL:
        if result.extracted_entities.cas_number is None:
            logger.warning(
                "Chemical SKU %r: CAS number could not be extracted.",
                sku_name,
            )