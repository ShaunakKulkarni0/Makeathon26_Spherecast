"""
Logic Layer/matcher.py

Layer 2, steps 2.2 and 2.3.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from embedder import load_all_embeddings, load_embedding          # noqa: E402
from src.database.legacy.shared.openai_client import chat_completion                   # noqa: E402
from shared.constants import (                                     # noqa: E402
    VECTOR_SEARCH_TOP_K,
    COSINE_SIMILARITY_THRESHOLD,
    JUDGE_MODEL,
)

logger = logging.getLogger(__name__)

# --- NEUES DATEN-SCHEMA ---
@dataclass
class GroupJudgeResult:
    sku_id_a: str = ""
    sku_id_b: str = ""
    cosine_similarity: float = 0.0
    belongs_to_same_group: bool = False
    group_title: str = ""
    alternative_group_title_b: str = ""
    reasoning: str = ""

# ---------------------------------------------------------------------------
# LLM judge system prompt
# ---------------------------------------------------------------------------
_JUDGE_SYSTEM_PROMPT = """\
You are an expert procurement taxonomy AI, specialized in grouping raw materials for sourcing consolidation.
I will provide you with TWO canonical description strings.
Your job is to determine if they belong to the EXACT SAME general purchasing group.

CRITICAL GROUPING RULES:
1. Chemical Synonyms MATCH: Common names and their chemical equivalents are the EXACT SAME material. For example, "Vitamin C" and "Ascorbic Acid" MUST be grouped together. "Vitamin D3" and "Cholecalciferol" MUST be grouped together. "Vitamin B1" and "Thiamine" MUST be grouped together.
2. Ignore Physical Form: Ignore differences like "powder", "liquid", "capsule", or "oil". They belong in the same group.
3. Ignore Brand Names: Treat branded ingredients and their generic equivalents as the same group.
4. Keep Distinct Salts/Molecules Separate: Do not mix different chemical compounds. "Magnesium Citrate" and "Magnesium Oxide" are DIFFERENT groups because the chemical properties and bioavailability differ.

If they belong together, generate a broad, standardized group title. If applicable, use the format "Chemical Name (Common Name)", e.g., "Ascorbic Acid (Vitamin C)".
If they do NOT belong together, indicate false and propose a separate, distinct group title for Material B.

You MUST respond with ONLY valid JSON — no markdown fences, no preamble:
{
  "belongs_to_same_group": true,
  "group_title": "Standardized Broad Title for the group",
  "alternative_group_title_b": "Title for Material B if they do NOT match (leave empty if true)",
  "reasoning": "1-2 sentences explaining why they are grouped together or separated based on the rules."
}
"""

# ---------------------------------------------------------------------------
# Step 2.2 — Vector search
# ---------------------------------------------------------------------------
def _cosine_similarity(a: list[float], b: list[float]) -> float:
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
    target_sku_id: str,
    top_k: int = VECTOR_SEARCH_TOP_K,
    threshold: float = COSINE_SIMILARITY_THRESHOLD,
) -> list[tuple[str, float]]:
    target_vector = load_embedding(conn, target_sku_id)
    if target_vector is None:
        raise ValueError(f"No embedding found for sku_id={target_sku_id}.")

    all_embeddings = load_all_embeddings(conn)
    scored: list[tuple[str, float]] = []
    for sku_id, vector in all_embeddings:
        if sku_id == target_sku_id:
            continue
        try:
            sim = _cosine_similarity(target_vector, vector)
        except ValueError:
            continue
        if sim >= threshold:
            scored.append((sku_id, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

# ---------------------------------------------------------------------------
# Step 2.3 — LLM judge
# ---------------------------------------------------------------------------
def _fetch_canonical_string(conn: sqlite3.Connection, sku_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT canonical_string FROM Product WHERE SKU = ?", (sku_id,)
    ).fetchone()
    return row[0] if row else None

def judge_pair(
    conn: sqlite3.Connection,
    sku_id_a: str,
    sku_id_b: str,
    cosine_similarity: float,
    model: str = JUDGE_MODEL,
) -> GroupJudgeResult:
    
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

def _parse_judge_response(raw_text: str, sku_id_a: str, sku_id_b: str) -> GroupJudgeResult:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(l for l in lines if not l.startswith("```")).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM judge returned invalid JSON: {raw_text[:300]}") from exc

    try:
        result = GroupJudgeResult(
            belongs_to_same_group=bool(data.get("belongs_to_same_group", False)),
            group_title=data.get("group_title", "Unknown Group"),
            alternative_group_title_b=data.get("alternative_group_title_b", ""),
            reasoning=data.get("reasoning", "")
        )
    except Exception as exc:
        raise ValueError(f"Schema validation failed: {exc}. Data: {data}") from exc

    return result