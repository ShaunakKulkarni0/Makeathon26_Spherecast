"""
Logic Layer/embedder.py

Layer 2, step 2.1 — Batch embedding.

Responsibilities:
  - Pull canonical_strings from the Product table (set by Layer 1).
  - Embed them using text-embedding-3-large via the OpenAI Embeddings API.
  - Persist the resulting vectors to the sku_embeddings table for ANN search.

The embeddings table uses BLOB storage for portability (SQLite has no native
vector type). For production, swap to a pgvector column in PostgreSQL — the
interface remains identical, only _write_embedding() changes.
"""
from __future__ import annotations

import logging
import sqlite3
import struct
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.database.legacy.shared.openai_client import create_embeddings
from shared.constants import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_BATCH_SIZE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialization helpers (float list ↔ BLOB)
# ---------------------------------------------------------------------------

def _vector_to_blob(vector: list[float]) -> bytes:
    """Pack a float list into a compact binary BLOB (little-endian float32)."""
    return struct.pack(f"<{len(vector)}f", *vector)


def _blob_to_vector(blob: bytes) -> list[float]:
    """Unpack a BLOB back to a list of float32 values."""
    n = len(blob) // 4  # 4 bytes per float32
    return list(struct.unpack(f"<{n}f", blob))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_embeddings_table(conn: sqlite3.Connection) -> None:
    """Create sku_embeddings table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sku_embeddings (
            sku_id    INTEGER PRIMARY KEY REFERENCES Product(Id),
            model     TEXT    NOT NULL,
            embedding BLOB    NOT NULL,
            dims      INTEGER NOT NULL
        )
        """
    )
    conn.commit()


def _fetch_skus_without_embedding(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
) -> list[tuple[int, str]]:
    """
    Return (Id, canonical_string) for raw-material SKUs that have a canonical_string
    but no entry in sku_embeddings yet.
    """
    query = (
        "SELECT p.Id, p.canonical_string FROM Product p "
        "LEFT JOIN sku_embeddings e ON e.sku_id = p.Id "
        "WHERE p.Type = 'raw-material' "
        "  AND p.canonical_string IS NOT NULL "
        "  AND p.canonical_string != '' "
        "  AND e.sku_id IS NULL "
        "ORDER BY p.Id"
    )
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    return [(r[0], r[1]) for r in rows]


def _write_embedding(
    conn: sqlite3.Connection,
    sku_id: int,
    vector: list[float],
    model: str,
) -> None:
    """Upsert one embedding row."""
    blob = _vector_to_blob(vector)
    conn.execute(
        """
        INSERT INTO sku_embeddings (sku_id, model, embedding, dims)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(sku_id) DO UPDATE SET
            model     = excluded.model,
            embedding = excluded.embedding,
            dims      = excluded.dims
        """,
        (sku_id, model, blob, len(vector)),
    )


def load_embedding(conn: sqlite3.Connection, sku_id: int) -> Optional[list[float]]:
    """
    Load a stored embedding vector for a given sku_id.
    Returns None if no embedding exists yet.
    """
    row = conn.execute(
        "SELECT embedding FROM sku_embeddings WHERE sku_id = ?", (sku_id,)
    ).fetchone()
    if row is None:
        return None
    return _blob_to_vector(row[0])


def load_all_embeddings(conn: sqlite3.Connection) -> list[tuple[int, list[float]]]:
    """
    Load all stored embeddings.
    Returns list of (sku_id, vector) tuples.
    """
    rows = conn.execute(
        "SELECT sku_id, embedding FROM sku_embeddings ORDER BY sku_id"
    ).fetchall()
    return [(r[0], _blob_to_vector(r[1])) for r in rows]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_embedding(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    batch_size: int = EMBEDDING_BATCH_SIZE,
    model: str = EMBEDDING_MODEL,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> int:
    """
    Embed all canonical strings that don't yet have a stored vector.

    Args:
        conn:       Active SQLite connection.
        limit:      Max SKUs to embed. None = all.
        batch_size: Number of strings per OpenAI embeddings API call.
        model:      Embedding model identifier.
        dimensions: Expected embedding dimensionality (for validation).

    Returns:
        Number of SKUs successfully embedded.
    """
    _ensure_embeddings_table(conn)

    pending = _fetch_skus_without_embedding(conn, limit=limit)
    logger.info("Embedder: %d SKU(s) pending embedding.", len(pending))

    if not pending:
        logger.info("All SKUs already embedded. Nothing to do.")
        return 0

    total_embedded = 0

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start : batch_start + batch_size]
        sku_ids    = [row[0] for row in batch]
        canon_strs = [row[1] for row in batch]

        logger.info(
            "Embedding batch %d–%d of %d …",
            batch_start + 1,
            batch_start + len(batch),
            len(pending),
        )

        try:
            vectors = create_embeddings(canon_strs, model=model, dimensions=dimensions)
        except Exception as exc:
            logger.error("Embedding API call failed for batch starting at %d: %s", batch_start, exc)
            continue

        for sku_id, vector in zip(sku_ids, vectors):
            try:
                _write_embedding(conn, sku_id, vector, model)
                total_embedded += 1
            except Exception as exc:
                logger.error("Failed to write embedding for sku_id=%d: %s", sku_id, exc)

        conn.commit()
        logger.debug("Committed %d embeddings.", len(batch))

    logger.info("Embedder complete. %d SKU(s) embedded.", total_embedded)
    return total_embedded