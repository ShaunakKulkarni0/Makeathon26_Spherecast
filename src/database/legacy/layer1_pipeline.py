from __future__ import annotations
import argparse
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "layers"))

from src.database.legacy.normalizer import normalize_sku_batch
from shared.schemas import NormalizationResult
from shared.constants import NORMALIZATION_BATCH_SIZE
from src.database.legacy.prompt_builder import build_normalization_prompt
from src.database.legacy.schema_discovery import load_schema, discover_schema

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


def _count_skus(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM Product WHERE Type='raw-material'"
    ).fetchone()[0]


def _fetch_unnormalized(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    force: bool = False,
) -> list[tuple[int, str]]:
    base_query = "SELECT Id, SKU FROM Product WHERE Type='raw-material'"
    if not force:
        base_query += " AND (canonical_string IS NULL OR canonical_string = '')"
    query = base_query + " ORDER BY Id"
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    print(f"\n[Layer 1] {len(rows)} SKU(s) gefunden (force={force})")
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


def _get_or_discover_schema(conn: sqlite3.Connection) -> dict | None:
    schema = load_schema(conn)
    if schema is not None:
        print(f"[Layer 1] Schema geladen: {schema.get('dataset_domain')}")
        return schema

    print("[Layer 1] Kein Schema gefunden — starte Discovery...")
    sample_size = min(200, _count_skus(conn))
    if sample_size == 0:
        print("[Layer 1] Keine SKUs fuer Discovery vorhanden.")
        return None

    schema = discover_schema(conn, sample_size=sample_size)
    dims = [d["dimension"] for d in schema.get("critical_dimensions", [])]
    print(f"[Layer 1] Schema entdeckt: {schema.get('dataset_domain')}")
    print(f"[Layer 1] Kritische Dimensionen: {dims}")
    return schema


def run_layer1(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    batch_size: int = NORMALIZATION_BATCH_SIZE,
    force: bool = False,
) -> list[NormalizationResult]:

    _ensure_columns(conn)
    schema = _get_or_discover_schema(conn)

    pending = _fetch_unnormalized(conn, limit=limit, force=force)
    if not pending:
        print("[Layer 1] Nichts zu verarbeiten.")
        return []

    completed: list[NormalizationResult] = []

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start : batch_start + batch_size]
        print(f"\n[Layer 1] Batch {batch_start + 1}-{batch_start + len(batch)} / {len(pending)}")

        results = normalize_sku_batch(batch, schema=schema)

        for result in results:
            try:
                _write_result(conn, result)
                completed.append(result)
            except Exception as exc:
                logger.error("DB write failed for sku_id=%s: %s", result.sku_id, exc)

        print(f"[Layer 1] {len(results)} SKU(s) gespeichert.")

    return completed


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Layer 1 - SKU normalization")
    p.add_argument("--db",        required=True)
    p.add_argument("--limit",     type=int, default=None)
    p.add_argument("--force",     action="store_true")
    p.add_argument("--log-level", default="INFO",
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
        results = run_layer1(conn, limit=args.limit, force=args.force)
        print(f"\nDone. {len(results)} SKU(s) normalisiert.")
    finally:
        conn.close()
