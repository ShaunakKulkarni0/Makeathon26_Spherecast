"""
group.py
--------
Reads all raw-material Products from the SQLite database, uses the OpenAI
o4-mini API to assign each compound to a canonical ingredient group
(e.g. "ascorbic acid" → "Vitamin C"), and writes the results to
compound_groups.csv with columns: group_name, product_id, supplier_ids, supplier_names.

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
    """Return all raw-material products plus supplier links for the CSV output."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.Id, p.SKU, sp.SupplierId, s.Name
        FROM Product p
        LEFT JOIN Supplier_Product sp ON p.Id = sp.ProductId
        LEFT JOIN Supplier s ON s.Id = sp.SupplierId
        WHERE p.Type = 'raw-material'
        """
    )
    rows = cur.fetchall()
    conn.close()

    products: dict[int, dict] = {}
    for product_id, sku, supplier_id, supplier_name in rows:
        if product_id not in products:
            products[product_id] = {
                "id": product_id,
                "sku": sku,
                "compound_name": extract_compound_name(sku),
                "supplier_ids": [],
                "supplier_names": [],
            }
        if supplier_id is not None:
            products[product_id]["supplier_ids"].append(str(supplier_id))
        if supplier_name:
            products[product_id]["supplier_names"].append(supplier_name)

    for product in products.values():
        product["supplier_ids"] = ";".join(sorted(set(product["supplier_ids"]), key=int))
        # Preserve insertion order for supplier names while removing duplicates
        seen: set[str] = set()
        unique_names: list[str] = []
        for name in product["supplier_names"]:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)
        product["supplier_names"] = ";".join(unique_names)

    return list(products.values())


def annotate_with_suppliers(results: list[dict], product_map: dict[int, dict]) -> None:
    """Attach supplier IDs and names to result rows based on product_id."""
    for row in results:
        product_id_value = row.get("product_id")
        try:
            product_id = int(product_id_value)
        except (TypeError, ValueError):
            product_id = 0
        product = product_map.get(product_id)
        row["supplier_ids"] = product["supplier_ids"] if product else ""
        row["supplier_names"] = product["supplier_names"] if product else ""


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


def read_existing_csv(input_path: str) -> list[dict]:
    """Read an existing grouped CSV and preserve its row order."""
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def write_csv(results: list[dict], out_path: str, sort_by_group: bool = True) -> None:
    """Write CSV and optionally sort by group_name; preserve input order if requested."""
    if sort_by_group:
        results = sorted(results, key=lambda r: (r.get("group_name", "").lower(), int(r.get("product_id", 0))))

    if results:
        fieldnames = list(results[0].keys())
        if "supplier_ids" not in fieldnames:
            fieldnames.append("supplier_ids")
        if "supplier_names" not in fieldnames:
            fieldnames.append("supplier_names")
    else:
        fieldnames = ["group_name", "product_id", "supplier_ids", "supplier_names"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Group DB compounds via o4-mini.")
    parser.add_argument("--db", default="db.sqlite", help="Path to SQLite database")
    parser.add_argument("--input", "--in", dest="input_csv", default=None,
                        help="Existing grouped CSV path to annotate")
    parser.add_argument("--out", default="compound_groups.csv", help="Output CSV path")
    parser.add_argument(
        "--batch", type=int, default=20,
        help="Number of compounds per API call (default: 20)"
    )
    parser.add_argument(
        "--model", default="o4-mini",
        help="OpenAI model to use (default: o4-mini)"
    )
    parser.add_argument(
        "--annotate-only", action="store_true",
        help="Only annotate an existing CSV with supplier data; do not call OpenAI."
    )
    parser.add_argument(
        "--preserve-order", action="store_true",
        help="Preserve input CSV order instead of sorting by group."
    )
    args = parser.parse_args()

    if args.annotate_only:
        print(f"Loading products from {args.db} …")
        products = load_products(args.db)
        print(f"  Found {len(products)} raw-material products.")
        product_map = {product["id"]: product for product in products}

        if not args.input_csv:
            sys.exit("ERROR: --annotate-only requires --input <existing CSV>")
        print(f"Reading existing CSV from {args.input_csv} …")
        all_results = read_existing_csv(args.input_csv)
        annotate_with_suppliers(all_results, product_map)
        print(f"\nWriting {len(all_results)} rows to {args.out} …")
        write_csv(all_results, args.out, sort_by_group=not args.preserve_order)
        return

    api_key = os.getenv("OpenAIAPI")
    if not api_key:
        sys.exit("ERROR: OpenAIAPI not found. Add it to your .env file.")

    client = OpenAI(api_key=api_key)

    print(f"Loading products from {args.db} …")
    products = load_products(args.db)
    print(f"  Found {len(products)} raw-material products.")
    product_map = {product["id"]: product for product in products}

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

    for result in all_results:
        product = product_map.get(result["product_id"])
        result["supplier_ids"] = product["supplier_ids"] if product else ""
        result["supplier_names"] = product["supplier_names"] if product else ""

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