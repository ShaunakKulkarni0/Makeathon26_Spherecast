"""
Data Layer/layer1_pipeline.py

Layer 1 orchestrator — ties together:
  1. DB fetch  : pull raw SKU rows that haven't been normalized yet
  2. Normalize : call the LLM via normalizer.normalize_sku()
  3. DB write  : persist canonical_string + extracted metadata back to the DB

Usage (CLI):
    python -m "Data Layer.layer1_pipeline" --db path/to/db.sqlite [--limit 100]

Usage (programmatic):
    from Data_Layer.layer1_pipeline import run_layer1
    run_layer1(conn, limit=None)
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path resolution — make shared/ importable when running as __main__
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from normalizer import normalize_sku, normalize_sku_batch  # noqa: E402
from shared.schemas import NormalizationResult             # noqa: E402
from shared.constants import NORMALIZATION_BATCH_SIZE      # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helpers (layer-1 specific — only reads/writes the columns it owns)
# ---------------------------------------------------------------------------

def _ensure_columns(conn: sqlite3.Connection) -> None:
    """
    Add Layer-1 output columns to the Product table if they don't exist yet.
    Safe to call on every run (uses IF NOT EXISTS semantics via try/except).
    """
    for col, col_type in [
        ("canonical_string",        "TEXT"),
        ("sku_category",            "TEXT"),
        ("cas_number",              "TEXT"),
        ("dosage_or_concentration", "TEXT"),
        ("chiral_form",             "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE Product ADD COLUMN {col} {col_type}")
            conn.commit()
            logger.debug("Added column Product.%s", col)
        except sqlite3.OperationalError:
            # Column already exists — this is expected on subsequent runs
            pass


def _fetch_unnormalized(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
) -> list[tuple[int, str]]:
    """
    Return (Id, SKU) rows from Product where canonical_string IS NULL.
    Only raw-material rows are candidates for normalization.
    """
    query = (
        "SELECT Id, SKU FROM Product "
        "WHERE Type='raw-material' AND (canonical_string IS NULL OR canonical_string = '') "
        "ORDER BY Id"
    )
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    return [(r[0], r[1]) for r in rows]


def _write_result(conn: sqlite3.Connection, result: NormalizationResult) -> None:
    """
    Persist a single NormalizationResult to the Product table.
    """
    conn.execute(
        """
        UPDATE Product SET
            canonical_string        = ?,
            sku_category            = ?,
            cas_number              = ?,
            dosage_or_concentration = ?,
            chiral_form             = ?
        WHERE Id = ?
        """,
        (
            result.canonical_string,
            result.category.value,
            result.extracted_entities.cas_number,
            result.extracted_entities.dosage_or_concentration,
            result.extracted_entities.chiral_form,
            result.sku_id,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_layer1(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    batch_size: int = NORMALIZATION_BATCH_SIZE,
) -> list[NormalizationResult]:
    """
    Run the full Layer 1 pipeline on all un-normalized raw-material SKUs.

    Args:
        conn:       Active SQLite connection (with row_factory = sqlite3.Row).
        limit:      Max number of SKUs to process. None = all.
        batch_size: How many SKUs to process per batch before committing.

    Returns:
        List of successfully persisted NormalizationResult objects.
    """
    _ensure_columns(conn)

    pending = _fetch_unnormalized(conn, limit=limit)
    logger.info("Layer 1: %d SKU(s) pending normalization.", len(pending))

    if not pending:
        logger.info("Nothing to do.")
        return []

    completed: list[NormalizationResult] = []

    # Process in batches to get periodic progress logs
    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start : batch_start + batch_size]
        logger.info(
            "Processing batch %d–%d of %d …",
            batch_start + 1,
            batch_start + len(batch),
            len(pending),
        )

        results = normalize_sku_batch(batch)

        for result in results:
            try:
                _write_result(conn, result)
                completed.append(result)
                logger.debug("Saved canonical_string for sku_id=%s", result.sku_id)
            except Exception as exc:
                logger.error(
                    "DB write failed for sku_id=%s: %s", result.sku_id, exc
                )

    logger.info("Layer 1 complete. %d/%d SKU(s) normalized.", len(completed), len(pending))
    return completed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Spherecast Layer 1 — SKU normalization pipeline")
    p.add_argument("--db",    required=True, help="Path to db.sqlite")
    p.add_argument("--limit", type=int, default=None, help="Max SKUs to process (default: all)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
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
        results = run_layer1(conn, limit=args.limit)
        print(f"\nDone. {len(results)} SKU(s) normalized and saved.")
    finally:
        conn.close()