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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "layers"))

from normalizer import normalize_sku, normalize_sku_batch  # noqa: E402
from shared.schemas import NormalizationResult             # noqa: E402
from shared.constants import NORMALIZATION_BATCH_SIZE      # noqa: E402

logger = logging.getLogger(__name__)


def _ensure_columns(conn: sqlite3.Connection) -> None:
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
        except sqlite3.OperationalError:
            pass


def _fetch_unnormalized(
    conn: sqlite3.Connection, 
    limit: Optional[int] = None,
    force: bool = False
) -> list[tuple[int, str]]:
    
    # Wenn force=True, holen wir ALLE raw-materials. Wenn False, nur die leeren.
    base_query = "SELECT Id, SKU FROM Product WHERE Type='raw-material'"
    
    if not force:
        base_query += " AND (canonical_string IS NULL OR canonical_string = '')"
        
    query = base_query + " ORDER BY Id"
    
    if limit:
        query += f" LIMIT {limit}"
        
    rows = conn.execute(query).fetchall()
    
    print(f"\n🛠️ [DEBUG - LAYER 1] DB Query beendet: {len(rows)} 'raw-material' SKUs gefunden (Force Override: {force}).")
    return [(r[0], r[1]) for r in rows]


def _write_result(conn: sqlite3.Connection, result: NormalizationResult) -> None:
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


def run_layer1(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    batch_size: int = NORMALIZATION_BATCH_SIZE,
    force: bool = False
) -> list[NormalizationResult]:
    
    _ensure_columns(conn)

    pending = _fetch_unnormalized(conn, limit=limit, force=force)
    logger.info("Layer 1: %d SKU(s) pending normalization.", len(pending))

    if not pending:
        print("🛠️ [DEBUG - LAYER 1] Keine SKUs zum Verarbeiten übrig. Beende Vorgang.")
        return []

    completed: list[NormalizationResult] = []

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start : batch_start + batch_size]
        
        print(f"\n🛠️ [DEBUG - LAYER 1] === START BATCH {batch_start + 1} bis {batch_start + len(batch)} ===")
        print(f"🛠️ [DEBUG - LAYER 1] Übergebe folgende SKUs an das LLM (normalizer.py):")
        for sid, sname in batch[:3]:
            print(f"    - ID: {sid} | Name: '{sname}'")
        if len(batch) > 3:
            print(f"    - ... und {len(batch) - 3} weitere.")

        # Hier wird OpenAI angerufen
        results = normalize_sku_batch(batch)

        print(f"🛠️ [DEBUG - LAYER 1] Antwort von LLM für {len(results)} SKUs erhalten! Schreibe in DB...")
        for result in results:
            try:
                _write_result(conn, result)
                completed.append(result)
                print(f"🛠️ [DEBUG - LAYER 1] Gespeichert -> ID {result.sku_id}: {result.category.value} | CAS: {result.extracted_entities.cas_number} | String: '{result.canonical_string[:60]}...'")
            except Exception as exc:
                logger.error("DB write failed for sku_id=%s: %s", result.sku_id, exc)

        print(f"🛠️ [DEBUG - LAYER 1] Batch abgeschlossen!\n")

    return completed


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Spherecast Layer 1 — SKU normalization pipeline")
    p.add_argument("--db",    required=True, help="Path to db.sqlite")
    p.add_argument("--limit", type=int, default=None, help="Max SKUs to process (default: all)")
    p.add_argument("--force", action="store_true", help="Erzwingt das Überschreiben bereits existierender Einträge")
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
        results = run_layer1(conn, limit=args.limit, force=args.force)
        print(f"\nDone. {len(results)} SKU(s) normalized and saved.")
    finally:
        conn.close()