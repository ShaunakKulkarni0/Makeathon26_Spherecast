"""
check_product_data_enrichment.py
────────────────────────────────
Identifies products linked to scrapable suppliers by:
1. Extracting SKU / ProductId / Supplier name from the SQLite database.
2. Fuzzy-matching DB supplier names against the evaluated CSV.
3. Mapping llm_evaluation statuses and writing a sorted output CSV.

Output → database/scrapable_products.csv
"""

import os
import sqlite3
from difflib import SequenceMatcher

import pandas as pd

# ── paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/database
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))               # project root
DB_PATH = os.path.join(PROJECT_ROOT, "db.sqlite")
CSV_PATH = os.path.join(BASE_DIR, "suppliers_filtered_evaluated.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "scrapable_products.csv")

# ── constants ────────────────────────────────────────────────────────────────
FUZZY_THRESHOLD = 0.90  # 90 % similarity required for a fuzzy match

STATUS_MAP = {
    "VIABLE":         "Viable",
    "NO_DATA":        "No Data",
    "REQUIRES_LOGIN": "Login",
}

# Custom sort order: Viable (0) → No Data (1) → Login (2) → anything else (3)
SCRAPABLE_SORT_ORDER = {"Viable": 0, "No Data": 1, "Login": 2}


def _normalize(name: str) -> str:
    """Lowercase + strip whitespace for comparison."""
    return name.strip().lower()


def _fuzzy_match(db_name: str, csv_name: str) -> bool:
    """
    Return True if the two supplier names should be considered the same.

    Strategy (case-insensitive):
      1. Exact match after normalisation.
      2. One string is a substring of the other.
      3. SequenceMatcher ratio ≥ FUZZY_THRESHOLD.
    """
    a, b = _normalize(db_name), _normalize(csv_name)
    if a == b:
        return True
    if a in b or b in a:
        return True
    if SequenceMatcher(None, a, b).ratio() >= FUZZY_THRESHOLD:
        return True
    return False


def _build_csv_lookup(csv_df: pd.DataFrame) -> dict:
    """
    Build a lookup dict from the evaluated CSV:
        { csv_name → { "llm_evaluation": ..., "website": ..., "name": ... } }
    """
    lookup: dict[str, dict] = {}
    for _, row in csv_df.iterrows():
        name = str(row["name"]).strip()
        lookup[name] = {
            "llm_evaluation": str(row.get("llm_evaluation", "NO_DATA")).strip(),
            "website":        str(row.get("website", "")).strip(),
            "name":           name,
        }
    return lookup


def _resolve_supplier(db_supplier_name: str,
                       csv_lookup: dict) -> dict:
    """
    Find the best match in the CSV lookup for a given DB supplier name.
    Returns a dict with keys: llm_evaluation, website, csv_name.
    Falls back to "No Data" when no match is found.
    """
    for csv_name, info in csv_lookup.items():
        if _fuzzy_match(db_supplier_name, csv_name):
            return {
                "llm_evaluation": info["llm_evaluation"],
                "website":        info["website"],
                "csv_name":       info["name"],
            }
    # No match → default
    return {
        "llm_evaluation": "NO_DATA",
        "website":        "",
        "csv_name":       db_supplier_name,
    }


def main() -> None:
    # ── 1. Load CSV lookup ───────────────────────────────────────────────────
    csv_df = pd.read_csv(CSV_PATH)
    csv_lookup = _build_csv_lookup(csv_df)
    print(f"Loaded {len(csv_lookup)} suppliers from CSV.")

    # ── 2. Query SQLite ──────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT p.SKU   AS SKU,
               p.Id    AS productId,
               s.Name  AS supplier_name
        FROM   Product          p
        JOIN   Supplier_Product sp ON p.Id   = sp.ProductId
        JOIN   Supplier         s  ON s.Id   = sp.SupplierId
        WHERE  p.Type != 'finished-good'
    """
    db_df = pd.read_sql_query(query, conn)
    conn.close()
    print(f"Fetched {len(db_df)} product-supplier rows from DB.")

    # ── 3. Fuzzy-match & map statuses ────────────────────────────────────────
    records: list[dict] = []
    # Cache resolved suppliers so we don't re-match for every row
    resolved_cache: dict[str, dict] = {}

    for _, row in db_df.iterrows():
        db_name = row["supplier_name"]

        if db_name not in resolved_cache:
            resolved_cache[db_name] = _resolve_supplier(db_name, csv_lookup)

        resolved = resolved_cache[db_name]
        raw_eval = resolved["llm_evaluation"]
        scrapable = STATUS_MAP.get(raw_eval, "No Data")  # default unmapped → No Data

        records.append({
            "SKU":        row["SKU"],
            "productId":  row["productId"],
            "company":    db_name,
            "url":        resolved["website"],
            "name":       resolved["csv_name"],
            "Scrapable":  scrapable,
        })

    out_df = pd.DataFrame(records)

    # ── 4. Sort: Scrapable status order → SKU ascending ──────────────────────
    out_df["_sort_key"] = out_df["Scrapable"].map(
        lambda s: SCRAPABLE_SORT_ORDER.get(s, 3)
    )
    out_df.sort_values(by=["_sort_key", "SKU"], ascending=[True, True], inplace=True)
    out_df.drop(columns=["_sort_key"], inplace=True)
    out_df.reset_index(drop=True, inplace=True)

    # ── 5. Write output ─────────────────────────────────────────────────────
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(out_df)} rows to {OUTPUT_PATH}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\nScrapable distribution:")
    print(out_df["Scrapable"].value_counts().to_string())


if __name__ == "__main__":
    main()
