"""
group.py
--------
Reads all raw-material Products from the SQLite database, uses the OpenAI
o4-mini API to assign each compound to a canonical ingredient group
(e.g. "ascorbic acid" → "Vitamin C"), and writes the results to
compound_groups.csv with columns: group_name, product_id.

Usage:
    python group.py --db path/to/db.sqlite [--out compound_groups.csv] [--batch 20]

Requirements:
    pip install openai python-dotenv
    .env must contain: OpenAIAPI=sk-...
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

SYSTEM_PROMPT = """\
You are a pharmaceutical / nutraceutical ingredient expert.
You will receive a list of raw-material compound names (one per line, with their product IDs).
For each compound, assign it to a canonical ingredient GROUP.

Rules:
- Group synonyms and chemically equivalent forms together.
  Examples:
    ascorbic acid, sodium ascorbate, calcium ascorbate  → "Vitamin C"
    cholecalciferol, ergocalciferol, vitamin d3         → "Vitamin D"
    cyanocobalamin, methylcobalamin                     → "Vitamin B12"
    pyridoxine hcl, pyridoxal-5-phosphate               → "Vitamin B6"
    thiamine hcl, thiamine mononitrate                  → "Vitamin B1"
    riboflavin, riboflavin-5-phosphate                  → "Vitamin B2"
    retinyl palmitate, vitamin a acetate, beta-carotene → "Vitamin A"
    tocopherol, d-alpha-tocopheryl succinate            → "Vitamin E"
    niacinamide, niacin, nicotinic acid                 → "Vitamin B3"
    d-calcium pantothenate, pantothenic acid            → "Vitamin B5"
    magnesium stearate, magnesium oxide, magnesium glycinate → "Magnesium"
    calcium citrate, calcium carbonate, dicalcium phosphate  → "Calcium"
- If a compound belongs to a clear functional/chemical family, use that family name.
- If a compound is truly unique (e.g. a proprietary botanical extract), create a specific group name for it.
- Group names must be title-cased, concise, and reusable across products.
- Return ONLY valid JSON — no markdown, no explanation — in this exact format:
  [
    {"product_id": 123, "group_name": "Vitamin C"},
    {"product_id": 456, "group_name": "Magnesium"},
    ...
  ]
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_compound_name(sku: str) -> str:
    """Strip RM-Cx- prefix and trailing 8-char hex hash from a raw-material SKU."""
    name = re.sub(r"^RM-[A-Z0-9]+-", "", sku)
    name = re.sub(r"-[a-f0-9]{8}$", "", name)
    return name.replace("-", " ").strip()


def load_products(db_path: str) -> list[dict]:
    """Return all raw-material products as list of {id, sku, compound_name}."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT Id, SKU FROM Product WHERE Type = 'raw-material'")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": row[0], "sku": row[1], "compound_name": extract_compound_name(row[1])}
        for row in rows
    ]


def batch_classify(client: OpenAI, products: list[dict], model: str = "o4-mini") -> list[dict]:
    """
    Send a batch of products to the model and return a list of
    {product_id, group_name} dicts.
    """
    lines = "\n".join(
        f"product_id={p['id']}: {p['compound_name']}" for p in products
    )
    user_message = f"Classify these compounds into groups:\n\n{lines}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw = response.choices[0].message.content.strip()
    # Strip possible markdown fences
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    return json.loads(raw)


def write_csv(results: list[dict], out_path: str) -> None:
    """Write group_name, product_id CSV sorted by group_name."""
    results_sorted = sorted(results, key=lambda r: (r["group_name"].lower(), r["product_id"]))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["group_name", "product_id"])
        writer.writeheader()
        writer.writerows(results_sorted)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Group DB compounds via o4-mini.")
    parser.add_argument("--db", default="db.sqlite", help="Path to SQLite database")
    parser.add_argument("--out", default="compound_groups.csv", help="Output CSV path")
    parser.add_argument(
        "--batch", type=int, default=20,
        help="Number of compounds per API call (default: 20)"
    )
    parser.add_argument(
        "--model", default="o4-mini",
        help="OpenAI model to use (default: o4-mini)"
    )
    args = parser.parse_args()

    api_key = os.getenv("OpenAIAPI")
    if not api_key:
        sys.exit("ERROR: OpenAIAPI not found. Add it to your .env file.")

    client = OpenAI(api_key=api_key)

    print(f"Loading products from {args.db} …")
    products = load_products(args.db)
    print(f"  Found {len(products)} raw-material products.")

    all_results: list[dict] = []
    total_batches = (len(products) + args.batch - 1) // args.batch

    for i in range(0, len(products), args.batch):
        batch = products[i : i + args.batch]
        batch_num = i // args.batch + 1
        print(f"  Batch {batch_num}/{total_batches}: classifying {len(batch)} compounds …", end=" ", flush=True)

        retries = 3
        for attempt in range(retries):
            try:
                results = batch_classify(client, batch, model=args.model)
                all_results.extend(results)
                print(f"OK ({len(results)} groups assigned)")
                break
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"Parse error on attempt {attempt + 1}: {exc}")
                if attempt < retries - 1:
                    time.sleep(2)
                else:
                    print("  Skipping batch after repeated failures.")
            except Exception as exc:
                print(f"API error on attempt {attempt + 1}: {exc}")
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    print("  Skipping batch after repeated failures.")

        # Small pause between batches to respect rate limits
        if batch_num < total_batches:
            time.sleep(0.5)

    print(f"\nWriting {len(all_results)} rows to {args.out} …")
    write_csv(all_results, args.out)

    # Summary statistics
    groups: dict[str, int] = {}
    for r in all_results:
        groups[r["group_name"]] = groups.get(r["group_name"], 0) + 1

    print(f"\nDone. {len(groups)} unique groups created.")
    print("\nTop 15 groups by size:")
    for name, count in sorted(groups.items(), key=lambda x: -x[1])[:15]:
        print(f"  {name:<40} {count:>4} products")


if __name__ == "__main__":
    main()