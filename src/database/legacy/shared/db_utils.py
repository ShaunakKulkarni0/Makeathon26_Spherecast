"""
db_utils.py — Database utilities for the Spherecast Agnes hackathon.

Schema overview:
  Company(Id, Name)
  Product(Id, SKU, CompanyId, Type)          Type ∈ {'finished-good', 'raw-material'}
  BOM(Id, ProducedProductId)
  BOM_Component(BOMId, ConsumedProductId)
  Supplier(Id, Name)
  Supplier_Product(SupplierId, ProductId)

SKU patterns:
  Finished goods  →  FG-iherb-{iherb_id}
  Raw materials   →  RM-C{CompanyId}-{ingredient-slug}-{8-char-hash}

=============================================================================
Method Overview (Inputs & Outputs)
=============================================================================
Note: All functions (except `get_connection` and `get_iherb_url`) require an 
active `sqlite3.Connection` object as their first argument (`conn`).

1. Connection Helper
-----------------------------------------------------------------------------
* get_connection(db_path: str)
  -> Returns: sqlite3.Connection (with row_factory enabled)

2. Basic Fetchers
-----------------------------------------------------------------------------
* get_all_companies(conn) 
  -> Returns: list[Company]
* get_company_by_id(conn, company_id: int) 
  -> Returns: Optional[Company]
* get_company_by_name(conn, name: str) 
  -> Returns: Optional[Company]

* get_all_products(conn) 
  -> Returns: list[Product]
* get_product_by_id(conn, product_id: int) 
  -> Returns: Optional[Product]
* get_products_by_company(conn, company_id: int) 
  -> Returns: list[Product]
* get_raw_materials(conn, company_id: Optional[int] = None) 
  -> Returns: list[Product]
* get_finished_goods(conn, company_id: Optional[int] = None) 
  -> Returns: list[Product]

* get_all_suppliers(conn) 
  -> Returns: list[Supplier]
* get_supplier_by_id(conn, supplier_id: int) 
  -> Returns: Optional[Supplier]

3. BOM Queries (Bill of Materials)
-----------------------------------------------------------------------------
* get_bom_for_product(conn, finished_good_id: int) 
  -> Returns: Optional[BOM] (includes component_product_ids)
* get_bom_components_as_products(conn, finished_good_id: int) 
  -> Returns: list[Product] (raw materials)
* get_all_boms(conn) 
  -> Returns: list[BOM]
* get_finished_goods_using_ingredient_slug(conn, ingredient_slug: str) 
  -> Returns: list[tuple[Product, Product]] (pairs of FinishedGood, RawMaterial)

4. Supplier Queries
-----------------------------------------------------------------------------
* get_suppliers_for_product(conn, product_id: int) 
  -> Returns: list[Supplier]
* get_products_for_supplier(conn, supplier_id: int, product_type: Optional[str] = None) 
  -> Returns: list[Product]
* get_supplier_coverage(conn) 
  -> Returns: dict[str, list[str]] (Map: supplier_name -> list of ingredient_slugs)

5. Consolidation / Substitution Analysis
-----------------------------------------------------------------------------
* get_ingredient_map(conn) 
  -> Returns: dict[str, list[Product]] (Map: ingredient_slug -> list of raw materials)
* get_consolidation_opportunities(conn, min_companies: int = 2, min_suppliers: int = 1) 
  -> Returns: list[ConsolidationOpportunity] (sorted by impact)
* get_opportunity_detail(conn, ingredient_slug: str) 
  -> Returns: dict (Comprehensive breakdown of an ingredient's usage and sourcing)
* get_ingredients_shared_between_companies(conn, company_id_a: int, company_id_b: int) 
  -> Returns: list[str] (Shared ingredient slugs)
* get_company_ingredient_matrix(conn) 
  -> Returns: dict[int, set[str]] (Map: company_id -> set of ingredient_slugs)
* get_supplier_ingredient_overlap(conn) 
  -> Returns: dict[str, set[str]] (Map: 'SupplierA|SupplierB' -> set of common ingredient_slugs)

6. iHerb URL Helpers
-----------------------------------------------------------------------------
* get_iherb_url(product: Product) 
  -> Returns: Optional[str]
* get_iherb_urls_for_company(conn, company_id: int) 
  -> Returns: dict[str, str] (Map: sku -> iHerb URL)

7. Summary / Stats (LLM Context Prep)
-----------------------------------------------------------------------------
* get_db_summary(conn) 
  -> Returns: dict (High-level counts of tables/entities)
* get_top_consolidation_opportunities(conn, top_n: int = 20) 
  -> Returns: list[dict] (Ranked plain-dict summary of top opportunities)
"""

import sqlite3
import re
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Company:
    id: int
    name: str

@dataclass
class Product:
    id: int
    sku: str
    company_id: int
    type: str  # 'finished-good' | 'raw-material'

    @property
    def is_raw_material(self) -> bool:
        return self.type == "raw-material"

    @property
    def is_finished_good(self) -> bool:
        return self.type == "finished-good"

    @property
    def ingredient_slug(self) -> Optional[str]:
        """
        Parse the human-readable ingredient name from a raw-material SKU.
        e.g. 'RM-C1-magnesium-stearate-fdedf242'  →  'magnesium-stearate'
        Returns None for finished goods.
        """
        if not self.is_raw_material:
            return None
        parts = self.sku.split("-")
        # parts[0] = 'RM', parts[1] = 'C{N}', parts[-1] = hash, middle = ingredient
        if len(parts) < 4:
            return None
        return "-".join(parts[2:-1])

    @property
    def iherb_id(self) -> Optional[str]:
        """Return the iHerb product ID for finished goods, else None."""
        if not self.is_finished_good:
            return None
        m = re.match(r"FG-iherb-(\d+)", self.sku)
        return m.group(1) if m else None

@dataclass
class Supplier:
    id: int
    name: str

@dataclass
class BOM:
    id: int
    produced_product_id: int
    component_product_ids: list[int] = field(default_factory=list)

@dataclass
class ConsolidationOpportunity:
    """
    Represents a group of per-company raw-material records that all refer
    to the same ingredient and are therefore candidates for consolidation.
    """
    ingredient_slug: str
    # product_id → (company_id, [supplier_names])
    entries: dict[int, tuple[int, list[str]]] = field(default_factory=dict)

    @property
    def company_ids(self) -> set[int]:
        return {v[0] for v in self.entries.values()}

    @property
    def supplier_names(self) -> set[str]:
        return {s for _, suppliers in self.entries.values() for s in suppliers}

    @property
    def n_companies(self) -> int:
        return len(self.company_ids)

    @property
    def n_suppliers(self) -> int:
        return len(self.supplier_names)


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Basic fetchers
# ---------------------------------------------------------------------------

def get_all_companies(conn: sqlite3.Connection) -> list[Company]:
    rows = conn.execute("SELECT Id, Name FROM Company ORDER BY Id").fetchall()
    return [Company(id=r["Id"], name=r["Name"]) for r in rows]

def get_company_by_id(conn: sqlite3.Connection, company_id: int) -> Optional[Company]:
    r = conn.execute("SELECT Id, Name FROM Company WHERE Id = ?", (company_id,)).fetchone()
    return Company(id=r["Id"], name=r["Name"]) if r else None

def get_company_by_name(conn: sqlite3.Connection, name: str) -> Optional[Company]:
    r = conn.execute("SELECT Id, Name FROM Company WHERE Name = ?", (name,)).fetchone()
    return Company(id=r["Id"], name=r["Name"]) if r else None


def get_all_products(conn: sqlite3.Connection) -> list[Product]:
    rows = conn.execute("SELECT Id, SKU, CompanyId, Type FROM Product ORDER BY Id").fetchall()
    return [Product(id=r["Id"], sku=r["SKU"], company_id=r["CompanyId"], type=r["Type"]) for r in rows]

def get_product_by_id(conn: sqlite3.Connection, product_id: int) -> Optional[Product]:
    r = conn.execute("SELECT Id, SKU, CompanyId, Type FROM Product WHERE Id = ?", (product_id,)).fetchone()
    return Product(id=r["Id"], sku=r["SKU"], company_id=r["CompanyId"], type=r["Type"]) if r else None

def get_products_by_company(conn: sqlite3.Connection, company_id: int) -> list[Product]:
    rows = conn.execute(
        "SELECT Id, SKU, CompanyId, Type FROM Product WHERE CompanyId = ? ORDER BY Id",
        (company_id,)
    ).fetchall()
    return [Product(id=r["Id"], sku=r["SKU"], company_id=r["CompanyId"], type=r["Type"]) for r in rows]

def get_raw_materials(conn: sqlite3.Connection, company_id: Optional[int] = None) -> list[Product]:
    if company_id is not None:
        rows = conn.execute(
            "SELECT Id, SKU, CompanyId, Type FROM Product WHERE Type='raw-material' AND CompanyId=? ORDER BY Id",
            (company_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT Id, SKU, CompanyId, Type FROM Product WHERE Type='raw-material' ORDER BY Id"
        ).fetchall()
    return [Product(id=r["Id"], sku=r["SKU"], company_id=r["CompanyId"], type=r["Type"]) for r in rows]

def get_finished_goods(conn: sqlite3.Connection, company_id: Optional[int] = None) -> list[Product]:
    if company_id is not None:
        rows = conn.execute(
            "SELECT Id, SKU, CompanyId, Type FROM Product WHERE Type='finished-good' AND CompanyId=? ORDER BY Id",
            (company_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT Id, SKU, CompanyId, Type FROM Product WHERE Type='finished-good' ORDER BY Id"
        ).fetchall()
    return [Product(id=r["Id"], sku=r["SKU"], company_id=r["CompanyId"], type=r["Type"]) for r in rows]


def get_all_suppliers(conn: sqlite3.Connection) -> list[Supplier]:
    rows = conn.execute("SELECT Id, Name FROM Supplier ORDER BY Id").fetchall()
    return [Supplier(id=r["Id"], name=r["Name"]) for r in rows]

def get_supplier_by_id(conn: sqlite3.Connection, supplier_id: int) -> Optional[Supplier]:
    r = conn.execute("SELECT Id, Name FROM Supplier WHERE Id = ?", (supplier_id,)).fetchone()
    return Supplier(id=r["Id"], name=r["Name"]) if r else None


# ---------------------------------------------------------------------------
# BOM queries
# ---------------------------------------------------------------------------

def get_bom_for_product(conn: sqlite3.Connection, finished_good_id: int) -> Optional[BOM]:
    """Return the BOM (with component IDs) for a given finished good product ID."""
    r = conn.execute("SELECT Id, ProducedProductId FROM BOM WHERE ProducedProductId = ?", (finished_good_id,)).fetchone()
    if not r:
        return None
    bom = BOM(id=r["Id"], produced_product_id=r["ProducedProductId"])
    comp_rows = conn.execute(
        "SELECT ConsumedProductId FROM BOM_Component WHERE BOMId = ?", (bom.id,)
    ).fetchall()
    bom.component_product_ids = [c["ConsumedProductId"] for c in comp_rows]
    return bom

def get_bom_components_as_products(conn: sqlite3.Connection, finished_good_id: int) -> list[Product]:
    """Return the raw-material Product objects that make up a finished good's BOM."""
    bom = get_bom_for_product(conn, finished_good_id)
    if not bom:
        return []
    return [get_product_by_id(conn, pid) for pid in bom.component_product_ids]

def get_all_boms(conn: sqlite3.Connection) -> list[BOM]:
    """Return all BOMs with their component lists."""
    bom_rows = conn.execute("SELECT Id, ProducedProductId FROM BOM").fetchall()
    boms = []
    for r in bom_rows:
        bom = BOM(id=r["Id"], produced_product_id=r["ProducedProductId"])
        comp_rows = conn.execute(
            "SELECT ConsumedProductId FROM BOM_Component WHERE BOMId = ?", (bom.id,)
        ).fetchall()
        bom.component_product_ids = [c["ConsumedProductId"] for c in comp_rows]
        boms.append(bom)
    return boms

def get_finished_goods_using_ingredient_slug(
    conn: sqlite3.Connection, ingredient_slug: str
) -> list[tuple[Product, Product]]:
    """
    Find all (finished_good, raw_material) pairs where the raw material's
    ingredient slug matches the given slug.
    Useful to understand what end products are affected by a sourcing decision.
    """
    rms = get_raw_materials(conn)
    matching_rm_ids = {rm.id for rm in rms if rm.ingredient_slug == ingredient_slug}
    if not matching_rm_ids:
        return []

    results = []
    for bom in get_all_boms(conn):
        overlap = matching_rm_ids & set(bom.component_product_ids)
        if overlap:
            fg = get_product_by_id(conn, bom.produced_product_id)
            for rm_id in overlap:
                rm = get_product_by_id(conn, rm_id)
                results.append((fg, rm))
    return results


# ---------------------------------------------------------------------------
# Supplier queries
# ---------------------------------------------------------------------------

def get_suppliers_for_product(conn: sqlite3.Connection, product_id: int) -> list[Supplier]:
    rows = conn.execute(
        """
        SELECT s.Id, s.Name FROM Supplier s
        JOIN Supplier_Product sp ON sp.SupplierId = s.Id
        WHERE sp.ProductId = ?
        """,
        (product_id,)
    ).fetchall()
    return [Supplier(id=r["Id"], name=r["Name"]) for r in rows]

def get_products_for_supplier(conn: sqlite3.Connection, supplier_id: int,
                               product_type: Optional[str] = None) -> list[Product]:
    """Return all products a given supplier can supply, optionally filtered by type."""
    query = """
        SELECT p.Id, p.SKU, p.CompanyId, p.Type FROM Product p
        JOIN Supplier_Product sp ON sp.ProductId = p.Id
        WHERE sp.SupplierId = ?
    """
    args = [supplier_id]
    if product_type:
        query += " AND p.Type = ?"
        args.append(product_type)
    rows = conn.execute(query, args).fetchall()
    return [Product(id=r["Id"], sku=r["SKU"], company_id=r["CompanyId"], type=r["Type"]) for r in rows]

def get_supplier_coverage(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """
    Return a map of supplier_name → [ingredient_slugs] they can supply.
    """
    rows = conn.execute(
        """
        SELECT s.Name, p.SKU FROM Supplier_Product sp
        JOIN Supplier s ON s.Id = sp.SupplierId
        JOIN Product p ON p.Id = sp.ProductId
        WHERE p.Type = 'raw-material'
        """
    ).fetchall()
    coverage: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        p = Product(id=0, sku=r["SKU"], company_id=0, type="raw-material")
        slug = p.ingredient_slug
        if slug:
            coverage[r["Name"]].append(slug)
    return dict(coverage)


# ---------------------------------------------------------------------------
# Consolidation / substitution analysis
# ---------------------------------------------------------------------------

def get_ingredient_map(conn: sqlite3.Connection) -> dict[str, list[Product]]:
    """
    Return a map of ingredient_slug → [Product, ...] across ALL companies.
    This is the core data structure for substitution analysis.
    """
    rms = get_raw_materials(conn)
    result: dict[str, list[Product]] = defaultdict(list)
    for rm in rms:
        slug = rm.ingredient_slug
        if slug:
            result[slug].append(rm)
    return dict(result)

def get_consolidation_opportunities(
    conn: sqlite3.Connection,
    min_companies: int = 2,
    min_suppliers: int = 1,
) -> list[ConsolidationOpportunity]:
    """
    Find ingredients bought by multiple companies (potentially from different suppliers).
    Returns a list of ConsolidationOpportunity objects, sorted by number of companies desc.

    Args:
        min_companies:  only return ingredients bought by at least this many companies
        min_suppliers:  only return ingredients with at least this many distinct suppliers
    """
    ingredient_map = get_ingredient_map(conn)
    opportunities = []

    for slug, products in ingredient_map.items():
        company_ids = {p.company_id for p in products}
        if len(company_ids) < min_companies:
            continue

        opp = ConsolidationOpportunity(ingredient_slug=slug)
        for p in products:
            suppliers = get_suppliers_for_product(conn, p.id)
            opp.entries[p.id] = (p.company_id, [s.name for s in suppliers])

        if opp.n_suppliers < min_suppliers:
            continue

        opportunities.append(opp)

    opportunities.sort(key=lambda o: (-o.n_companies, -o.n_suppliers))
    return opportunities

def get_opportunity_detail(
    conn: sqlite3.Connection, ingredient_slug: str
) -> dict:
    """
    Return a full detail dict for a single ingredient slug:
    - all raw-material products (with company names)
    - all suppliers per product
    - all finished goods that use this ingredient
    """
    companies = {c.id: c for c in get_all_companies(conn)}
    rms = [p for p in get_raw_materials(conn) if p.ingredient_slug == ingredient_slug]

    entries = []
    for rm in rms:
        company = companies.get(rm.company_id)
        suppliers = get_suppliers_for_product(conn, rm.id)
        entries.append({
            "product_id": rm.id,
            "sku": rm.sku,
            "company_id": rm.company_id,
            "company_name": company.name if company else "?",
            "suppliers": [s.name for s in suppliers],
        })

    affected_fgs = get_finished_goods_using_ingredient_slug(conn, ingredient_slug)
    affected = [
        {"finished_good_sku": fg.sku, "raw_material_sku": rm.sku, "company_id": fg.company_id}
        for fg, rm in affected_fgs
    ]

    all_suppliers = {s for e in entries for s in e["suppliers"]}

    return {
        "ingredient_slug": ingredient_slug,
        "n_companies": len({e["company_id"] for e in entries}),
        "n_suppliers": len(all_suppliers),
        "suppliers": sorted(all_suppliers),
        "entries": entries,
        "affected_finished_goods": affected,
    }

def get_ingredients_shared_between_companies(
    conn: sqlite3.Connection, company_id_a: int, company_id_b: int
) -> list[str]:
    """Return ingredient slugs that both companies purchase."""
    slugs_a = {p.ingredient_slug for p in get_raw_materials(conn, company_id_a) if p.ingredient_slug}
    slugs_b = {p.ingredient_slug for p in get_raw_materials(conn, company_id_b) if p.ingredient_slug}
    return sorted(slugs_a & slugs_b)

def get_company_ingredient_matrix(conn: sqlite3.Connection) -> dict[int, set[str]]:
    """Return a map of company_id → set of ingredient slugs they buy."""
    rms = get_raw_materials(conn)
    matrix: dict[int, set[str]] = defaultdict(set)
    for rm in rms:
        slug = rm.ingredient_slug
        if slug:
            matrix[rm.company_id].add(slug)
    return dict(matrix)

def get_supplier_ingredient_overlap(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """
    For each pair of suppliers, return the set of ingredient slugs both can supply.
    Useful for identifying which supplier could be the 'winner' in a consolidation.
    Returns dict keyed by 'SupplierA|SupplierB'.
    """
    coverage = get_supplier_coverage(conn)
    suppliers = list(coverage.keys())
    overlap = {}
    for i, a in enumerate(suppliers):
        for b in suppliers[i+1:]:
            common = set(coverage[a]) & set(coverage[b])
            if common:
                overlap[f"{a}|{b}"] = common
    return overlap


# ---------------------------------------------------------------------------
# iHerb URL helpers
# ---------------------------------------------------------------------------

IHERB_BASE = "https://www.iherb.com/pr/"

def get_iherb_url(product: Product) -> Optional[str]:
    """Return the iHerb URL for a finished good product, if available."""
    iid = product.iherb_id
    return f"{IHERB_BASE}{iid}" if iid else None

def get_iherb_urls_for_company(conn: sqlite3.Connection, company_id: int) -> dict[str, str]:
    """Return {sku: iherb_url} for all finished goods of a company."""
    fgs = get_finished_goods(conn, company_id)
    return {fg.sku: get_iherb_url(fg) for fg in fgs if fg.iherb_id}


# ---------------------------------------------------------------------------
# Summary / stats
# ---------------------------------------------------------------------------

def get_db_summary(conn: sqlite3.Connection) -> dict:
    """High-level stats about the database — useful for LLM context injection."""
    return {
        "n_companies": conn.execute("SELECT COUNT(*) FROM Company").fetchone()[0],
        "n_finished_goods": conn.execute("SELECT COUNT(*) FROM Product WHERE Type='finished-good'").fetchone()[0],
        "n_raw_materials": conn.execute("SELECT COUNT(*) FROM Product WHERE Type='raw-material'").fetchone()[0],
        "n_boms": conn.execute("SELECT COUNT(*) FROM BOM").fetchone()[0],
        "n_bom_components": conn.execute("SELECT COUNT(*) FROM BOM_Component").fetchone()[0],
        "n_suppliers": conn.execute("SELECT COUNT(*) FROM Supplier").fetchone()[0],
        "n_supplier_product_links": conn.execute("SELECT COUNT(*) FROM Supplier_Product").fetchone()[0],
    }

def get_top_consolidation_opportunities(
    conn: sqlite3.Connection, top_n: int = 20
) -> list[dict]:
    """
    Quick ranked list of the biggest consolidation opportunities as plain dicts.
    Suitable for printing or passing to an LLM.
    """
    opps = get_consolidation_opportunities(conn, min_companies=2)
    result = []
    for opp in opps[:top_n]:
        result.append({
            "ingredient_slug": opp.ingredient_slug,
            "n_companies": opp.n_companies,
            "n_suppliers": opp.n_suppliers,
            "suppliers": sorted(opp.supplier_names),
        })
    return result


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "db.sqlite"
    conn = get_connection(db_path)

    print("=== DB Summary ===")
    for k, v in get_db_summary(conn).items():
        print(f"  {k}: {v}")

    print("Suppliers")
    print(get_all_suppliers(conn))

    print("\n=== Top 10 Consolidation Opportunities ===")
    for opp in get_top_consolidation_opportunities(conn, top_n=10):
        print(f"  {opp['ingredient_slug']}: {opp['n_companies']} companies, "
              f"{opp['n_suppliers']} suppliers → {opp['suppliers']}")

    print("\n=== Detail: vitamin-d3-cholecalciferol ===")
    import json
    detail = get_opportunity_detail(conn, "vitamin-d3-cholecalciferol")
    print(f"  Companies: {detail['n_companies']}, Suppliers: {detail['suppliers']}")
    print(f"  Affected finished goods: {len(detail['affected_finished_goods'])}")

    print("\n=== iHerb URLs for Company 1 ===")
    for sku, url in list(get_iherb_urls_for_company(conn, 1).items())[:3]:
        print(f"  {sku} → {url}")

    conn.close()