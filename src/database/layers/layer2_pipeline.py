"""
Logic Layer/layer2_pipeline.py

Layer 2 orchestrator — ties together:
  2.1 Embedding  : embed all canonical strings not yet stored
  2.2 Search     : ANN cosine search, threshold filter
  2.3 LLM judge  : pairwise confidence + compliance flags
  2.4 Storage    : write results to the matches table

Usage (CLI):
    python -m "Logic Layer.layer2_pipeline" --db path/to/db.sqlite [--target-sku-id 42]

Usage (programmatic):
    from Logic_Layer.layer2_pipeline import run_layer2_for_sku, run_layer2_all
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from embedder import run_embedding                             # noqa: E402
from matcher  import vector_search, judge_pair                 # noqa: E402
from shared.schemas import JudgeResult                         # noqa: E402
from shared.constants import VECTOR_SEARCH_TOP_K, COSINE_SIMILARITY_THRESHOLD  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helpers — matches table
# ---------------------------------------------------------------------------

def _ensure_matches_table(conn: sqlite3.Connection) -> None:
    """Create the matches table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id_a          INTEGER NOT NULL REFERENCES Product(Id),
            sku_id_b          INTEGER NOT NULL REFERENCES Product(Id),
            cosine_similarity REAL    NOT NULL,
            confidence_level  TEXT    NOT NULL,
            compliance_flags  TEXT    NOT NULL DEFAULT '[]',
            reasoning         TEXT    NOT NULL,
            created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(sku_id_a, sku_id_b)
        )
        """
    )
    conn.commit()


def _write_match(conn: sqlite3.Connection, result: JudgeResult) -> None:
    """
    Insert or replace a match result.
    We always use the lower sku_id as sku_id_a to prevent duplicate (A,B)/(B,A) rows.
    """
    id_a = min(result.sku_id_a, result.sku_id_b)   # type: ignore[arg-type]
    id_b = max(result.sku_id_a, result.sku_id_b)   # type: ignore[arg-type]

    conn.execute(
        """
        INSERT INTO matches
            (sku_id_a, sku_id_b, cosine_similarity, confidence_level, compliance_flags, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(sku_id_a, sku_id_b) DO UPDATE SET
            cosine_similarity = excluded.cosine_similarity,
            confidence_level  = excluded.confidence_level,
            compliance_flags  = excluded.compliance_flags,
            reasoning         = excluded.reasoning,
            created_at        = datetime('now')
        """,
        (
            id_a,
            id_b,
            result.cosine_similarity,
            result.confidence_level.value,
            json.dumps([f.value for f in result.compliance_flags]),
            result.reasoning,
        ),
    )


def _already_judged(conn: sqlite3.Connection, sku_id_a: int, sku_id_b: int) -> bool:
    """Return True if this pair already has a match row (to avoid re-judging)."""
    id_a, id_b = min(sku_id_a, sku_id_b), max(sku_id_a, sku_id_b)
    row = conn.execute(
        "SELECT 1 FROM matches WHERE sku_id_a = ? AND sku_id_b = ?", (id_a, id_b)
    ).fetchone()
    return row is not None


def _fetch_all_raw_material_ids(conn: sqlite3.Connection) -> list[int]:
    """Return IDs of all raw-material SKUs that have a stored embedding."""
    rows = conn.execute(
        """
        SELECT p.Id FROM Product p
        JOIN sku_embeddings e ON e.sku_id = p.Id
        WHERE p.Type = 'raw-material'
        ORDER BY p.Id
        """
    ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Core matching logic (single SKU)
# ---------------------------------------------------------------------------

def run_layer2_for_sku(
    conn: sqlite3.Connection,
    target_sku_id: int,
    top_k: int = VECTOR_SEARCH_TOP_K,
    threshold: float = COSINE_SIMILARITY_THRESHOLD,
    skip_existing: bool = True,
) -> list[JudgeResult]:
    """
    Run steps 2.2 + 2.3 for a single target SKU.

    Args:
        conn:            Active SQLite connection.
        target_sku_id:   SKU to search against.
        top_k:           Number of ANN candidates to retrieve.
        threshold:       Minimum cosine similarity to pass to the judge.
        skip_existing:   If True, skip pairs that already have a match row.

    Returns:
        List of JudgeResult objects written to the matches table.
    """
    _ensure_matches_table(conn)

    # Step 2.2 — vector search
    candidates = vector_search(conn, target_sku_id, top_k=top_k, threshold=threshold)
    logger.info(
        "SKU %d: %d candidate(s) passed threshold %.2f.",
        target_sku_id, len(candidates), threshold,
    )

    if not candidates:
        return []

    results: list[JudgeResult] = []

    for candidate_id, similarity in candidates:
        if skip_existing and _already_judged(conn, target_sku_id, candidate_id):
            logger.debug("Pair (%d, %d) already judged — skipping.", target_sku_id, candidate_id)
            continue

        # Step 2.3 — LLM judge
        try:
            judge_result = judge_pair(
                conn,
                sku_id_a=target_sku_id,
                sku_id_b=candidate_id,
                cosine_similarity=similarity,
            )
        except Exception as exc:
            logger.error(
                "Judge failed for pair (%d, %d): %s",
                target_sku_id, candidate_id, exc,
            )
            continue

        # Step 2.4 — persist
        try:
            _write_match(conn, judge_result)
            conn.commit()
            results.append(judge_result)
            logger.info(
                "Match stored: (%d, %d) → %s  flags=%s",
                target_sku_id,
                candidate_id,
                judge_result.confidence_level.value,
                [f.value for f in judge_result.compliance_flags],
            )
        except Exception as exc:
            logger.error(
                "DB write failed for pair (%d, %d): %s",
                target_sku_id, candidate_id, exc,
            )

    return results


# ---------------------------------------------------------------------------
# Full pipeline (embed all + match all)
# ---------------------------------------------------------------------------

def run_layer2_all(
    conn: sqlite3.Connection,
    embed_limit: Optional[int] = None,
    skip_existing: bool = True,
) -> dict[str, int]:
    """
    Run the complete Layer 2 pipeline:
      1. Embed any un-embedded canonical strings (step 2.1).
      2. For every embedded SKU, run vector search + judge (steps 2.2/2.3).
      3. Persist results to the matches table (step 2.4).

    Args:
        conn:          Active SQLite connection.
        embed_limit:   Cap on SKUs to embed in step 2.1 (None = all).
        skip_existing: Skip pairs that already have match rows.

    Returns:
        Dict with 'embedded', 'skus_processed', 'matches_written' counts.
    """
    # Step 2.1
    n_embedded = run_embedding(conn, limit=embed_limit)

    # Steps 2.2 / 2.3 / 2.4
    all_ids = _fetch_all_raw_material_ids(conn)
    logger.info("Layer 2: running match pipeline for %d SKU(s).", len(all_ids))

    total_matches = 0
    for sku_id in all_ids:
        try:
            results = run_layer2_for_sku(conn, sku_id, skip_existing=skip_existing)
            total_matches += len(results)
        except Exception as exc:
            logger.error("Layer 2 failed for sku_id=%d: %s", sku_id, exc)

    summary = {
        "embedded":        n_embedded,
        "skus_processed":  len(all_ids),
        "matches_written": total_matches,
    }
    logger.info("Layer 2 complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Spherecast Layer 2 — embedding + matching pipeline")
    p.add_argument("--db",            required=True, help="Path to db.sqlite")
    p.add_argument("--target-sku-id", type=int, default=None,
                   help="Run steps 2.2/2.3 for a single SKU only (default: all)")
    p.add_argument("--embed-only",    action="store_true",
                   help="Only run step 2.1 (embedding), skip matching")
    p.add_argument("--force",         action="store_true",
                   help="Re-judge pairs that already have match rows")
    p.add_argument("--log-level",     default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        if args.embed_only:
            n = run_embedding(conn)
            print(f"Embedded {n} SKU(s).")
        elif args.target_sku_id is not None:
            # Single-SKU mode: embed if needed, then match
            run_embedding(conn)
            results = run_layer2_for_sku(
                conn,
                target_sku_id=args.target_sku_id,
                skip_existing=not args.force,
            )
            print(f"\n{len(results)} match(es) written for sku_id={args.target_sku_id}.")
            for r in results:
                flags = [f.value for f in r.compliance_flags]
                print(
                    f"  → sku_id={r.sku_id_b}  "
                    f"confidence={r.confidence_level.value}  "
                    f"cosine={r.cosine_similarity:.4f}  "
                    f"flags={flags}"
                )
        else:
            summary = run_layer2_all(conn, skip_existing=not args.force)
            print(f"\nLayer 2 complete: {summary}")
    finally:
        conn.close()