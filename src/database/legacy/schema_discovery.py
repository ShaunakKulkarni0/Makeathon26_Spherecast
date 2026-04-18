from __future__ import annotations
import json
import sqlite3
from src.database.legacy.shared.openai_client import chat_completion


def _ensure_schema_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dataset_schema (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def discover_schema(conn: sqlite3.Connection, sample_size: int = 200) -> dict:
    rows = conn.execute(
        """SELECT SKU FROM Product
           WHERE Type='raw-material'
           ORDER BY RANDOM()
           LIMIT ?""",
        (sample_size,)
    ).fetchall()

    sku_sample = [r[0] for r in rows]
    schema = _derive_schema_via_llm(sku_sample)
    _persist_schema(conn, schema)
    return schema


def _derive_schema_via_llm(sku_names: list[str]) -> dict:
    system_prompt = """\
You are an expert in supply chain data modeling.
You will receive a sample of raw material SKU names from a database.

Your task: Analyze these SKUs and identify the CRITICAL DISAMBIGUATION DIMENSIONS
for this specific dataset — i.e., what attributes, if different, mean two
seemingly similar SKUs are NOT substitutable.

Output ONLY valid JSON with this schema:
{
  "dataset_domain": "<e.g. nutraceuticals, chemicals, food ingredients, pharma excipients>",
  "critical_dimensions": [
    {
      "dimension": "<dimension name>",
      "why_critical": "<one sentence>",
      "examples_from_data": ["<sku1>", "<sku2>"],
      "extraction_instruction": "<exact instruction for how to extract this from a SKU name>"
    }
  ],
  "allergen_relevant": true/false,
  "regulatory_context": "<e.g. EU food law, US FDA, cosmetics INCI>",
  "common_ambiguities": [
    {
      "ambiguous_pattern": "<e.g. 'vitamin D' without D2/D3 specification>",
      "resolution_rule": "<e.g. always mark as unspecified form, never merge with D3>"
    }
  ]
}

Be specific to THIS dataset. Do not output generic rules."""

    user_content = "Sample SKU names:\n" + "\n".join(f"- {s}" for s in sku_names)

    raw = chat_completion(
        model="gpt-4o",
        system_prompt=system_prompt,
        user_content=user_content,
        json_mode=True,
        temperature=0.0,
    )

    return json.loads(raw)


def _persist_schema(conn: sqlite3.Connection, schema: dict) -> None:
    _ensure_schema_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO dataset_schema (key, value) VALUES (?, ?)",
        ("discovered_schema", json.dumps(schema))
    )
    conn.commit()


def load_schema(conn: sqlite3.Connection) -> dict | None:
    _ensure_schema_table(conn)  # <- jetzt immer erst Tabelle sicherstellen
    row = conn.execute(
        "SELECT value FROM dataset_schema WHERE key = 'discovered_schema'"
    ).fetchone()
    return json.loads(row[0]) if row else None
