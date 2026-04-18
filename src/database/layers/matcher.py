"""
Logic Layer/matcher.py

Layer 2, steps 2.2 and 2.3.

Step 2.2 — Vector search:
  - For a target SKU, compute cosine similarity against all stored embeddings.
  - Return the Top-K candidates above the hard threshold (0.65).

Step 2.3 — LLM judge:
  - For each candidate pair, call gpt-4o to classify confidence level and
    extract compliance flags.
  - Returns a validated JudgeResult per pair.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from embedder import load_all_embeddings, load_embedding          # noqa: E402
from shared.openai_client import chat_completion                   # noqa: E402
from shared.schemas import JudgeResult, ConfidenceLevel, ComplianceFlag  # noqa: E402
from shared.constants import (                                     # noqa: E402
    VECTOR_SEARCH_TOP_K,
    COSINE_SIMILARITY_THRESHOLD,
    JUDGE_MODEL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM judge system prompt
# ---------------------------------------------------------------------------
# The word "JSON" must appear in the system prompt (OpenAI requirement for
# response_format=json_object). It appears in the schema description below.
# ---------------------------------------------------------------------------
_JUDGE_SYSTEM_PROMPT = """\
You are an expert procurement verification AI.
I will provide you with TWO canonical description strings representing raw materials.
Your job is to determine if they are the exact same material, functionally \
substitutable, or just in the same category.

Evaluate based on:
1. Chemistry/CAS — CAS numbers must match for an "Exact" rating.
2. Dosage/Concentration — if one is 1 mg and the other 10 mg, they are NOT exact.
3. Chiral forms — L- vs D- are completely different materials.
4. Branded vs Generic — cannot substitute branded without a flag.

Confidence levels:
- "Exact"      : Identical chemical and function. Safe to consolidate.
- "Functional" : Same function, different form (e.g. Magnesium Citrate vs Magnesium Oxide).
- "Category"   : Same product family, but requires formulation change.
- "No Match"   : Different materials entirely.

Compliance flags (include all that apply, or return an empty array):
- "VEGAN_CONFLICT"        — one is animal-derived, the other plant-derived.
- "BIOAVAILABILITY_DELTA" — meaningfully different absorption rates.
- "LABELING_CLAIM_IMPACT" — switching would change label claims.
- "BRANDED_NO_SUB"        — one is a protected brand ingredient.

You MUST respond with ONLY valid JSON — no markdown fences, no preamble:
{
  "confidence_level": "Exact | Functional | Category | No Match",
  "reasoning": "2-3 sentences explaining your determination, explicitly referencing CAS numbers, dosage, or chiral form where relevant.",
  "compliance_flags": ["FLAG_1", "FLAG_2"]
}
"""


# ---------------------------------------------------------------------------
# Step 2.2 — Vector search
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Pure-Python cosine similarity.
    For production with pgvector, this is replaced by a native SQL operator (<=>).
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def vector_search(
    conn: sqlite3.Connection,
    target_sku_id: int,
    top_k: int = VECTOR_SEARCH_TOP_K,
    threshold: float = COSINE_SIMILARITY_THRESHOLD,
) -> list[tuple[int, float]]:
    """
    Find the most similar SKUs to `target_sku_id` by cosine similarity.

    Args:
        conn:          Active SQLite connection.
        target_sku_id: The SKU to match against.
        top_k:         Maximum number of candidates to return.
        threshold:     Minimum cosine similarity — pairs below this are dropped.

    Returns:
        List of (sku_id, cosine_similarity) sorted by similarity descending.
        The target SKU itself is excluded.

    Raises:
        ValueError: If the target SKU has no stored embedding.
    """
    target_vector = load_embedding(conn, target_sku_id)
    if target_vector is None:
        raise ValueError(
            f"No embedding found for sku_id={target_sku_id}. "
            "Run the embedder (layer2_pipeline.run_embedding) first."
        )

    all_embeddings = load_all_embeddings(conn)  # [(sku_id, vector), ...]

    scored: list[tuple[int, float]] = []
    for sku_id, vector in all_embeddings:
        if sku_id == target_sku_id:
            continue  # Don't compare a SKU to itself
        try:
            sim = _cosine_similarity(target_vector, vector)
        except ValueError:
            logger.warning("Dimension mismatch for sku_id=%d — skipping.", sku_id)
            continue
        if sim >= threshold:
            scored.append((sku_id, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Step 2.3 — LLM judge
# ---------------------------------------------------------------------------

def _fetch_canonical_string(conn: sqlite3.Connection, sku_id: int) -> Optional[str]:
    """Retrieve the canonical_string for a SKU from the Product table."""
    row = conn.execute(
        "SELECT canonical_string FROM Product WHERE Id = ?", (sku_id,)
    ).fetchone()
    return row[0] if row else None


def judge_pair(
    conn: sqlite3.Connection,
    sku_id_a: int,
    sku_id_b: int,
    cosine_similarity: float,
    model: str = JUDGE_MODEL,
) -> JudgeResult:
    """
    Call the LLM judge for a single candidate pair.

    Args:
        conn:             Active SQLite connection.
        sku_id_a:         Target SKU ID.
        sku_id_b:         Candidate SKU ID.
        cosine_similarity: The cosine similarity score from step 2.2.
        model:            LLM model to use.

    Returns:
        A validated JudgeResult with sku_id_a, sku_id_b, and cosine_similarity attached.

    Raises:
        ValueError: If either SKU is missing a canonical_string, or the LLM
                    returns a response that fails schema validation.
    """
    canon_a = _fetch_canonical_string(conn, sku_id_a)
    canon_b = _fetch_canonical_string(conn, sku_id_b)

    if not canon_a:
        raise ValueError(f"No canonical_string for sku_id_a={sku_id_a}")
    if not canon_b:
        raise ValueError(f"No canonical_string for sku_id_b={sku_id_b}")

    user_content = (
        f"Cosine similarity score: {cosine_similarity:.4f}\n\n"
        f"MATERIAL A (sku_id={sku_id_a}):\n{canon_a}\n\n"
        f"MATERIAL B (sku_id={sku_id_b}):\n{canon_b}"
    )

    logger.debug(
        "Judging pair sku_id_a=%d vs sku_id_b=%d (cosine=%.4f)",
        sku_id_a, sku_id_b, cosine_similarity,
    )

    raw_text = chat_completion(
        model=model,
        system_prompt=_JUDGE_SYSTEM_PROMPT,
        user_content=user_content,
        json_mode=True,
        temperature=0.0,
    )

    result = _parse_judge_response(raw_text, sku_id_a, sku_id_b)
    result.sku_id_a          = sku_id_a
    result.sku_id_b          = sku_id_b
    result.cosine_similarity = cosine_similarity
    return result

def vector_search_from_cache(
    target_id: int,
    embedding_map: dict[int, list[float]],
    top_k: int = VECTOR_SEARCH_TOP_K,
    threshold: float = COSINE_SIMILARITY_THRESHOLD,
) -> list[tuple[int, float]]:
    target_vec = embedding_map.get(target_id)
    if target_vec is None:
        raise ValueError(f"No embedding for sku_id={target_id}")

    scored = [
        (sid, _cosine_similarity(target_vec, vec))
        for sid, vec in embedding_map.items()
        if sid != target_id
    ]
    scored = [(sid, s) for sid, s in scored if s >= threshold]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _parse_judge_response(raw_text: str, sku_id_a: int, sku_id_b: int) -> JudgeResult:
    """Parse and validate the LLM judge JSON response."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(l for l in lines if not l.startswith("```")).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM judge returned invalid JSON for pair "
            f"({sku_id_a}, {sku_id_b}): {raw_text[:300]}"
        ) from exc

    try:
        flags = [ComplianceFlag(f) for f in data.get("compliance_flags", [])]
        result = JudgeResult(
            confidence_level=ConfidenceLevel(data["confidence_level"]),
            reasoning=data["reasoning"],
            compliance_flags=flags,
        )
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"LLM judge response failed schema validation for pair "
            f"({sku_id_a}, {sku_id_b}): {exc}. Data: {data}"
        ) from exc

    return result