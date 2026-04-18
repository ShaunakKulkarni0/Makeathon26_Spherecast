# CLAUDE.md — Data Layer
## spherecast-agnes / scrapers + data/

> This file is the single source of truth for any AI agent (Claude or otherwise)
> working inside `scrapers/`, `data/`, or `agents/ingestion_agent.py`.
> Read this entire file before writing or modifying any code in these directories.

---

## 1. What This Layer Does

The data layer has one job: **turn fragmented, messy, multi-format external sources
into clean, validated, schema-conformant JSON that the scoring engine can consume
without any further cleaning.**

The scoring engine (`scoring/`) and Agnes (`agents/agnes_agent.py`) are strict consumers.
They will never clean data themselves. If dirty data reaches them, the demo breaks.
The data layer is the firewall.

Pipeline:
```
External source → scraper → raw/ → ingestion_agent → processed/ → scoring engine
                                         ↑
                               validates, normalizes,
                               unit-converts, deduplicates
```

---

## 2. Directory Layout (data layer only)

```
spherecast-agnes/
├── data/
│   ├── raw/                        # Untouched scraper output. Never edited manually.
│   │   ├── plasticportal/          # HTML snapshots from plasticportal.eu
│   │   ├── borealis/               # Downloaded PDF spec sheets
│   │   ├── lyondellbasell/         # Downloaded PDF spec sheets
│   │   ├── echa/                   # EU compliance HTML/JSON
│   │   └── icis/                   # News snippets for Agnes context
│   ├── processed/                  # Validated, normalized MaterialRecord JSON
│   └── mock/
│       ├── disruption_event.json   # The PP force majeure trigger event
│       ├── materials_catalog.json  # 8–10 pre-loaded PP/rPP/PE/PET candidates
│       └── supplier_prices.json    # Current spot prices per grade, per region
│
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py             # Abstract base — all scrapers inherit from this
│   ├── plasticportal.py            # Live price table scraper
│   ├── borealis.py                 # PDF spec sheet downloader + text extractor
│   ├── lyondellbasell.py           # PDF spec sheet downloader + text extractor
│   └── echa.py                     # EU 10/2011 food contact compliance checker
│
└── agents/
    └── ingestion_agent.py          # Orchestrates scrapers, normalizes, validates, writes processed/
```

---

## 3. The Canonical Data Schema

**Every material that enters the scoring engine must conform to `MaterialRecord`.**
This is the contract between the data layer and everything above it.

```python
# agents/ingestion_agent.py — define this Pydantic model here, import everywhere

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum

class PolymerFamily(str, Enum):
    PP   = "PP"    # Polypropylene (virgin)
    rPP  = "rPP"   # Recycled polypropylene
    PE   = "PE"    # Polyethylene (generic)
    HDPE = "HDPE"
    LDPE = "LDPE"
    LLDPE = "LLDPE"
    PET  = "PET"
    ABS  = "ABS"
    PS   = "PS"
    BIO_PP = "BIO_PP"  # Bio-based polypropylene

class Region(str, Enum):
    EU_WEST      = "EU_WEST"
    EU_EAST      = "EU_EAST"
    NORTH_AMERICA = "NORTH_AMERICA"
    ASIA         = "ASIA"
    MIDDLE_EAST  = "MIDDLE_EAST"

class MaterialRecord(BaseModel):
    # --- Identity ---
    id: str                          # e.g. "borealis_bb412e_2026-04"  (supplier_grade_YYYY-MM)
    name: str                        # Human-readable: "Borealis BB412E"
    trade_name: Optional[str]        # e.g. "Bormed BB412E"
    supplier: str                    # e.g. "Borealis AG"
    polymer_family: PolymerFamily
    grade_designation: str           # Exact grade string from datasheet: "BB412E"
    is_recycled: bool = False
    is_bio_based: bool = False

    # --- Mechanical Properties (all required for PP substitution scoring) ---
    melt_flow_index_g10min: Optional[float]   # MFI at 230°C/2.16kg for PP; 190°C/2.16kg for PE
    mfi_test_conditions: Optional[str]        # e.g. "230°C/2.16kg" — store raw so scorer can validate
    tensile_strength_mpa: Optional[float]     # ISO 527, yield
    tensile_elongation_break_pct: Optional[float]
    flexural_modulus_mpa: Optional[float]     # ISO 178
    izod_notched_impact_kj_m2: Optional[float] # ISO 180, 23°C
    charpy_notched_impact_kj_m2: Optional[float]
    hardness_shore_d: Optional[float]
    density_g_cm3: Optional[float]            # ISO 1183

    # --- Thermal Properties ---
    vicat_softening_temp_c: Optional[float]   # ISO 306, method A
    heat_deflection_temp_c: Optional[float]   # ISO 75, 0.45 MPa
    melting_point_c: Optional[float]
    processing_temp_range_c: Optional[tuple[float, float]]  # (min, max)

    # --- Optical Properties (critical for packaging/beverage labels) ---
    haze_pct: Optional[float]         # ASTM D1003 — low = clearer film
    gloss_60deg: Optional[float]      # Higher = shinier, important for shrink labels

    # --- Compliance & Certifications ---
    eu_food_contact: bool = False              # EU Regulation 10/2011
    eu_food_contact_categories: List[str] = [] # e.g. ["FA", "FB", "FC"] — food types
    reach_compliant: bool = False
    rohs_compliant: bool = False
    fda_compliant: bool = False
    recycled_content_pct: Optional[float]      # 0–100
    certifications: List[str] = []             # ["ISO 9001", "ISCC PLUS", "REDcert²"]

    # --- Commercial Data (update frequently — these go stale fast) ---
    price_eur_per_kg: Optional[float]
    price_region: Optional[Region]
    price_date: Optional[str]                  # ISO 8601: "2026-04-17"
    price_type: Optional[str]                  # "spot" | "contract" | "list" | "estimated"
    lead_time_days: Optional[int]              # From order to delivery in EU
    moq_kg: Optional[int]                      # Minimum order quantity
    supplier_country: Optional[str]            # ISO 3166-1 alpha-2: "NL", "DE", "US"
    supply_risk: Optional[str]                 # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"

    # --- Provenance (for explainability and trust scoring) ---
    source_url: Optional[str]
    source_type: str                           # "datasheet_pdf" | "web_scrape" | "mock" | "manual"
    source_scraped_at: Optional[str]           # ISO 8601 datetime
    datasheet_path: Optional[str]             # Relative path to raw/ file
    confidence_score: float = 1.0             # 0.0–1.0: how much to trust extracted values
    extraction_notes: Optional[str]           # Flags anomalies: "MFI extrapolated from range"

    @validator("melt_flow_index_g10min")
    def mfi_reasonable_range(cls, v):
        if v is not None and not (0.1 <= v <= 2000):
            raise ValueError(f"MFI {v} outside plausible range [0.1, 2000] g/10min")
        return v

    @validator("density_g_cm3")
    def density_reasonable(cls, v):
        if v is not None and not (0.85 <= v <= 2.2):
            raise ValueError(f"Density {v} outside plausible polymer range")
        return v

    @validator("price_eur_per_kg")
    def price_reasonable(cls, v):
        if v is not None and not (0.3 <= v <= 25.0):
            raise ValueError(f"Price {v} EUR/kg outside plausible range — check units")
        return v
```

**Rule: If a field cannot be extracted and is Optional, set it to `None`. Never guess.
Set `confidence_score` lower and add an `extraction_note` instead.**

---

## 4. The Disruption Event Schema

Agnes is triggered by a disruption event. The data layer must also be able to
produce and validate this schema (used in `data/mock/disruption_event.json`).

```python
class DisruptionEvent(BaseModel):
    id: str                          # "disruption_pp_hormuz_2026-04"
    triggered_at: str                # ISO 8601
    disrupted_material: str          # polymer_family value: "PP"
    disrupted_grade: Optional[str]   # Specific grade if known: "Moplen HP500N"
    affected_supplier: str           # "LyondellBasell"
    disruption_type: str             # "force_majeure" | "shortage" | "price_spike" | "logistics"
    disruption_cause: str            # "Strait of Hormuz closure — Middle East conflict"
    severity: str                    # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    estimated_duration_weeks: Optional[int]
    price_impact_pct: Optional[float]  # +38.0 means 38% price increase
    affected_regions: List[Region]
    current_inventory_weeks: Optional[float]  # Brand's remaining stock in weeks
    weekly_consumption_kg: Optional[float]
    news_source_url: Optional[str]
    raw_news_snippet: Optional[str]   # Max 500 chars for Agnes context injection
```

---

## 5. Scraper Specifications

### 5.1 `scrapers/base_scraper.py`

All scrapers must inherit from this. Never instantiate directly.

```python
import httpx
import time
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SpherecastResearch/1.0; hackathon)",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}
REQUEST_DELAY_S = 1.5   # Be polite. Don't get IP-banned during the demo.
TIMEOUT_S = 15

class BaseScraper(ABC):
    source_name: str = "unknown"     # Override in subclass: "plasticportal"
    raw_subdir: str = "unknown"      # Override in subclass: "plasticportal"

    def __init__(self):
        self.raw_dir = RAW_DIR / self.raw_subdir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_html(self, url: str, cache_filename: str) -> str:
        """Fetch URL, cache raw HTML to raw/, return HTML string."""
        cache_path = self.raw_dir / cache_filename
        if cache_path.exists():
            self.logger.info(f"Cache hit: {cache_filename}")
            return cache_path.read_text(encoding="utf-8")
        time.sleep(REQUEST_DELAY_S)
        resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        cache_path.write_text(resp.text, encoding="utf-8")
        self.logger.info(f"Fetched and cached: {url}")
        return resp.text

    def fetch_pdf(self, url: str, filename: str) -> Path:
        """Download PDF, save to raw/, return Path."""
        pdf_path = self.raw_dir / filename
        if pdf_path.exists():
            return pdf_path
        time.sleep(REQUEST_DELAY_S)
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        pdf_path.write_bytes(resp.content)
        return pdf_path

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Return list of raw dicts — not yet MaterialRecord. Ingestion agent normalizes."""
        pass

    def save_raw_json(self, data: list[dict], filename: str):
        import json
        out = self.raw_dir / filename
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

---

### 5.2 `scrapers/plasticportal.py` — Live Price Scraper

**Target:** `https://www.plasticportal.eu/en/prices/`
**What to extract:** PP, rPP, PE, HDPE, LLDPE, PET price tables for Central Europe (EUR/kg)
**Update frequency:** Run at hackathon start, then every 2h during demo

```python
# Key extraction logic — implement fully:

PRICE_TARGET_MATERIALS = {
    "PP": ["PP homo", "PP copo", "PP random copo", "PP-H", "PP-R", "PP-C"],
    "PE": ["HDPE", "LDPE", "LLDPE", "MDPE"],
    "PET": ["PET bottle", "PET film"],
    "PS":  ["HIPS", "GPPS"],
}

# Expected HTML structure (as of April 2026):
# <table class="price-table"> with <tr> rows:
# [Material grade] [Price EUR/kg] [Change %] [Date]
# Use BeautifulSoup: soup.find_all("table", class_="price-table")

# Output raw dict format:
{
    "grade_raw": "PP random copo",           # exactly as scraped
    "price_eur_per_kg": 1.73,
    "change_pct": 23.4,
    "price_date": "2026-04-17",
    "region": "Central Europe",
    "source_url": "https://www.plasticportal.eu/en/prices/",
    "scraped_at": "2026-04-17T10:00:00"
}

# IMPORTANT: If plasticportal blocks or changes structure, fall back to:
# mock/supplier_prices.json — pre-loaded with April 2026 values
# PP random copo: 1.73 EUR/kg (+23% vs pre-crisis 1.40)
# HDPE film: 1.58 EUR/kg
# LLDPE: 1.62 EUR/kg
# rPP (Veolia est.): 1.61 EUR/kg
# PET bottle: 1.12 EUR/kg
```

---

### 5.3 `scrapers/borealis.py` — Spec Sheet Scraper

**Target:** Borealis AG product datasheet portal
**Priority grades for demo (scrape these first):**

| Grade | Application | Why relevant |
|---|---|---|
| BB412E | Injection moulding, food contact | Primary target material |
| HC101BF | Bimodal HDPE film | PE substitute candidate |
| BJ368MO | PP random copo, food contact | Best PP spec match candidate |
| RJ588MO | PP copo, packaging | Alternative candidate |

**PDF extraction strategy:**
```python
# Use pymupdf (fitz) — NOT pdfplumber for Borealis (their PDFs use embedded fonts)
import fitz  # pip install pymupdf

def extract_borealis_datasheet(pdf_path: Path) -> dict:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()

    # Borealis datasheet layout (consistent across grades as of 2024):
    # Section: "Physical Properties" → density, MFI
    # Section: "Mechanical Properties" → tensile, flexural, impact
    # Section: "Thermal Properties" → Vicat, HDT
    # Section: "Regulatory Information" → food contact status

    # Use regex patterns — Borealis uses consistent formatting:
    import re
    patterns = {
        "melt_flow_index_g10min": r"Melt Flow Rate.*?(\d+\.?\d*)\s*g/10min",
        "density_g_cm3":          r"Density.*?(\d+\.?\d*)\s*g/cm³",
        "tensile_strength_mpa":   r"Tensile Stress at Yield.*?(\d+\.?\d*)\s*MPa",
        "vicat_softening_temp_c": r"Vicat Softening Temperature.*?(\d+\.?\d*)\s*°C",
        "eu_food_contact":        r"(EU|European).*?10/2011|food contact",
    }
    # eu_food_contact: if pattern found → True, else False
    # All numeric: float(match.group(1)) if match else None
```

---

### 5.4 `scrapers/lyondellbasell.py` — Spec Sheet Scraper

**Target:** LyondellBasell product finder + PDF datasheets
**Priority grades:**

| Grade | Polymer | Notes |
|---|---|---|
| Moplen HP500N | PP homo | Most common EU packaging grade — the DISRUPTED material |
| Moplen EP300L | PP copo | Key substitute candidate |
| Petrothene GA501-020 | HDPE | PE substitute |
| Lupolen 3020D | LDPE film | Flexible film substitute |

**IMPORTANT — LyondellBasell force majeure context:**
LyondellBasell declared force majeure on several EU sites in March 2026.
When the scraper fetches their product pages, also check:
`https://www.lyondellbasell.com/en/news-releases/` for force majeure announcements.
Store any found FM announcements in `data/raw/icis/force_majeure_log.json`.
Agnes uses this to explain the disruption trigger to the user.

```python
# LyondellBasell uses a React SPA — static HTML scraping won't work.
# Use one of these two strategies:
#
# STRATEGY A (preferred, faster): Use their public PDF download links directly.
# URL pattern: https://www.lyondellbasell.com/49de6d/contentassets/[hash]/[grade].pdf
# Pre-discovered URLs for priority grades are hardcoded in the scraper (see below).
#
# STRATEGY B (fallback): playwright headless browser
# from playwright.sync_api import sync_playwright
# Launches Chromium, waits for JS render, then extracts table data.
# Slower (~8s per page) — only use if Strategy A URLs break.

LYONDELLBASELL_PDF_URLS = {
    "Moplen HP500N": "https://www.lyondellbasell.com/.../moplen-hp500n.pdf",  # fill at hackathon
    "Moplen EP300L": "https://www.lyondellbasell.com/.../moplen-ep300l.pdf",
}
# At hackathon start: manually navigate to each grade, copy the PDF URL, paste here.
# This takes 10 min but saves hours of debugging JS scraping.
```

---

### 5.5 `scrapers/echa.py` — EU Food Contact Compliance

**Target:** ECHA's EU Plastics Regulation 10/2011 substance database
**URL:** `https://echa.europa.eu/food-contact-materials`
**What to extract:** Whether a specific polymer grade/substance is permitted for food contact

```python
# EU 10/2011 compliance logic:
#
# The regulation lists permitted MONOMERS and ADDITIVES, not grades.
# A grade is food-contact compliant if:
#   1. Its polymer backbone monomer is listed (PP = propylene → listed as FCM substance 176)
#   2. Its additives are all listed in Annex I
#   3. Supplier explicitly states compliance on datasheet
#
# For our demo purposes, implement a two-track approach:

KNOWN_COMPLIANT_POLYMERS = {
    # polymer_family → True/False + categories
    "PP":    {"compliant": True,  "categories": ["FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH"]},
    "rPP":   {"compliant": True,  "categories": ["FA", "FB", "FC"], "note": "Requires EFSA dossier per batch"},
    "HDPE":  {"compliant": True,  "categories": ["FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH"]},
    "LDPE":  {"compliant": True,  "categories": ["FA", "FB", "FC", "FG"]},
    "LLDPE": {"compliant": True,  "categories": ["FA", "FB", "FC"]},
    "PET":   {"compliant": True,  "categories": ["FA", "FB", "FC", "FD", "FE"]},
    "ABS":   {"compliant": False, "categories": [], "note": "Not generally permitted for direct food contact"},
    "PS":    {"compliant": True,  "categories": ["FA"], "note": "Styrene migration limits apply"},
    "BIO_PP":{"compliant": True,  "categories": ["FA", "FB", "FC"], "note": "Same as fossil PP if identical structure"},
}

# For rPP specifically — this is a DEMO DIFFERENTIATOR:
# rPP from Veolia (ISCC PLUS certified) has an existing EFSA-approved dossier.
# Agnes can say: "Veolia rPP has an active EFSA food contact approval — no new testing required."
# This is a real selling point vs. untested recycled material.
```

---

## 6. `agents/ingestion_agent.py` — Full Specification

This is the most critical file in the data layer. It:
1. Calls all scrapers
2. Merges price data onto spec data
3. Normalizes units
4. Validates against MaterialRecord schema
5. Assigns confidence scores
6. Writes to `data/processed/`

### 6.1 Unit Normalization Rules

**Always convert to these canonical units before writing processed/:**

| Property | Canonical Unit | Common Raw Variants |
|---|---|---|
| MFI | g/10min | g/10 min, cm³/10min (×density), dg/min |
| Density | g/cm³ | kg/m³ (÷1000), g/cc |
| Tensile strength | MPa | N/mm² (=MPa), kPa (÷1000), psi (×0.00689) |
| Flexural modulus | MPa | GPa (×1000), kPa (÷1000) |
| Temperature | °C | °F ((F-32)×5/9), K (K-273.15) |
| Price | EUR/kg | EUR/t (÷1000), USD/kg (×0.92 approx), ct/kg (÷100) |
| Impact | kJ/m² | J/m (×0.001×width_m), ft-lb/in (×0.0534) |

```python
# Implement as pure functions in ingestion_agent.py:

def normalize_mfi(value: float, unit_raw: str) -> tuple[float, str]:
    """Returns (normalized_value, note_if_approximated)"""
    unit = unit_raw.lower().strip()
    if "dg/min" in unit:
        return value, ""            # dg/min == g/10min for most instruments
    if "cm³" in unit or "cc" in unit:
        # Need density to convert volume flow → mass flow
        # If density unknown: return value as-is, flag it
        return value, "cm³/10min assumed ≈ g/10min (density not applied)"
    return value, ""

def normalize_price(value: float, unit_raw: str, fx_usd_eur: float = 0.92) -> float:
    unit = unit_raw.lower()
    if "/t" in unit or "/tonne" in unit or "/ton" in unit:
        return value / 1000
    if "usd" in unit or "$" in unit:
        return value * fx_usd_eur
    if "ct/" in unit or "cent" in unit:
        return value / 100
    return value  # assume EUR/kg
```

### 6.2 Confidence Score Assignment

```python
def compute_confidence(record: dict) -> tuple[float, str]:
    """
    Returns (confidence_score 0.0–1.0, explanation string)

    Scoring logic:
    - Source is official PDF datasheet from supplier:   base = 0.95
    - Source is scraped from supplier product page:     base = 0.85
    - Source is market price aggregator (PlasticPortal): base = 0.80
    - Source is mock/manual:                            base = 0.70
    - Source is news article (for price estimates):     base = 0.55

    Deductions:
    - MFI test conditions not specified:               -0.05
    - Price older than 7 days:                         -0.10
    - Price older than 30 days:                        -0.20
    - Any unit conversion was approximated:            -0.05 per field
    - Food contact compliance inferred (not explicit): -0.15
    - >3 mechanical properties are None:               -0.10
    """
    score = 0.95
    notes = []

    if record.get("source_type") == "web_scrape":
        score -= 0.10
    if record.get("source_type") == "mock":
        score -= 0.25
    if not record.get("mfi_test_conditions"):
        score -= 0.05
        notes.append("MFI conditions unspecified")
    # ... etc

    return max(0.0, round(score, 2)), "; ".join(notes)
```

### 6.3 Deduplication Strategy

Multiple scrapers may return the same grade. Dedup rules:

```python
# Primary key for deduplication: (supplier.lower(), grade_designation.lower())
# If duplicate found:
#   - Keep the record with HIGHER confidence_score
#   - For price: always use the NEWER price_date
#   - Log merge: "Merged Borealis BB412E from datasheet + plasticportal price"
# Never silently discard — log every merge to data/processed/merge_log.json
```

### 6.4 Fallback to Mock Data

**This is critical for the demo.** If scrapers fail during presentation:

```python
def load_materials(use_cache: bool = True, fallback_to_mock: bool = True) -> list[MaterialRecord]:
    """
    Main entry point for scoring engine.
    Order of precedence:
    1. data/processed/ if files exist and are <4h old
    2. Run scrapers fresh
    3. Fall back to data/mock/materials_catalog.json (ALWAYS works)
    """
    processed_dir = Path("data/processed")
    files = sorted(processed_dir.glob("*.json"))

    if use_cache and files:
        newest = max(files, key=lambda f: f.stat().st_mtime)
        age_h = (time.time() - newest.stat().st_mtime) / 3600
        if age_h < 4:
            return [MaterialRecord(**json.loads(f.read_text())) for f in files]

    try:
        return run_all_scrapers()
    except Exception as e:
        if fallback_to_mock:
            logging.warning(f"Scrapers failed ({e}), using mock data")
            return load_mock_catalog()
        raise
```

---

## 7. Mock Data Specification

### `data/mock/disruption_event.json`

```json
{
  "id": "disruption_pp_hormuz_2026-04",
  "triggered_at": "2026-04-17T08:00:00Z",
  "disrupted_material": "PP",
  "disrupted_grade": "Moplen HP500N",
  "affected_supplier": "LyondellBasell",
  "disruption_type": "force_majeure",
  "disruption_cause": "Strait of Hormuz closure — Iran conflict restricts Middle East petrochemical exports",
  "severity": "CRITICAL",
  "estimated_duration_weeks": 8,
  "price_impact_pct": 38.0,
  "affected_regions": ["EU_WEST", "EU_EAST", "ASIA"],
  "current_inventory_weeks": 8.0,
  "weekly_consumption_kg": 5000,
  "news_source_url": "https://www.packagingdive.com/news/iran-war-packaging-effects-disruption-oil-aluminum-plastics/815156/",
  "raw_news_snippet": "LyondellBasell declared force majeure on several EU sites March 2026. PP prices surged 38% month-on-month as Strait of Hormuz disruptions cut Middle East petrochemical exports."
}
```

### `data/mock/materials_catalog.json`

Pre-load these 8 materials. Research their real specs before the hackathon:

```json
[
  {
    "id": "lyondellbasell_hp500n_2026-04",
    "name": "LyondellBasell Moplen HP500N",
    "supplier": "LyondellBasell",
    "polymer_family": "PP",
    "grade_designation": "HP500N",
    "is_recycled": false,
    "melt_flow_index_g10min": 12.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 35.0,
    "density_g_cm3": 0.900,
    "vicat_softening_temp_c": 153.0,
    "eu_food_contact": true,
    "reach_compliant": true,
    "price_eur_per_kg": 1.93,
    "price_region": "EU_WEST",
    "price_date": "2026-04-17",
    "price_type": "spot",
    "lead_time_days": 56,
    "supply_risk": "CRITICAL",
    "source_type": "mock",
    "confidence_score": 0.85,
    "extraction_notes": "Force majeure declared. Price reflects March 2026 crisis spot price."
  },
  {
    "id": "borealis_bj368mo_2026-04",
    "name": "Borealis BJ368MO",
    "supplier": "Borealis AG",
    "polymer_family": "PP",
    "grade_designation": "BJ368MO",
    "is_recycled": false,
    "melt_flow_index_g10min": 8.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 34.0,
    "density_g_cm3": 0.900,
    "vicat_softening_temp_c": 148.0,
    "eu_food_contact": true,
    "reach_compliant": true,
    "price_eur_per_kg": 1.88,
    "price_region": "EU_WEST",
    "price_date": "2026-04-17",
    "price_type": "spot",
    "lead_time_days": 21,
    "supply_risk": "MEDIUM",
    "source_type": "mock",
    "confidence_score": 0.85,
    "extraction_notes": "Borealis Stenungsund (Sweden) not affected by Hormuz disruption."
  },
  {
    "id": "veolia_rpp_iscc_2026-04",
    "name": "Veolia Polymers rPP ISCC PLUS",
    "trade_name": "Recy'PP Food",
    "supplier": "Veolia Polymers",
    "polymer_family": "rPP",
    "grade_designation": "Recy-PP-FC-12",
    "is_recycled": true,
    "recycled_content_pct": 100.0,
    "melt_flow_index_g10min": 11.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 32.0,
    "density_g_cm3": 0.905,
    "vicat_softening_temp_c": 148.0,
    "eu_food_contact": true,
    "eu_food_contact_categories": ["FA", "FB", "FC"],
    "reach_compliant": true,
    "certifications": ["ISCC PLUS", "ISO 9001", "EU 10/2011"],
    "price_eur_per_kg": 1.61,
    "price_region": "EU_WEST",
    "price_date": "2026-04-17",
    "price_type": "estimated",
    "lead_time_days": 12,
    "supplier_country": "NL",
    "supply_risk": "LOW",
    "source_type": "mock",
    "confidence_score": 0.80,
    "extraction_notes": "Price estimated from market reports. EFSA food contact dossier active. DEMO WINNER CANDIDATE."
  },
  {
    "id": "sabic_pp_579s_2026-04",
    "name": "SABIC PP 579S",
    "supplier": "SABIC Europe",
    "polymer_family": "PP",
    "grade_designation": "579S",
    "is_recycled": false,
    "melt_flow_index_g10min": 18.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 33.0,
    "density_g_cm3": 0.900,
    "vicat_softening_temp_c": 145.0,
    "eu_food_contact": true,
    "reach_compliant": true,
    "price_eur_per_kg": 1.99,
    "price_region": "EU_WEST",
    "price_date": "2026-04-17",
    "price_type": "spot",
    "lead_time_days": 35,
    "supplier_country": "NL",
    "supply_risk": "HIGH",
    "source_type": "mock",
    "confidence_score": 0.80,
    "extraction_notes": "SABIC has Middle East production — partial supply risk. MFI higher than target — Agnes should flag processing temp adjustment."
  },
  {
    "id": "ineos_hdpe_p003_2026-04",
    "name": "INEOS Polyolefins HDPE P003-55",
    "supplier": "INEOS Polyolefins",
    "polymer_family": "HDPE",
    "grade_designation": "P003-55",
    "is_recycled": false,
    "melt_flow_index_g10min": 0.3,
    "mfi_test_conditions": "190°C/2.16kg",
    "tensile_strength_mpa": 28.0,
    "density_g_cm3": 0.955,
    "eu_food_contact": true,
    "reach_compliant": true,
    "price_eur_per_kg": 1.55,
    "price_region": "EU_WEST",
    "price_date": "2026-04-17",
    "price_type": "spot",
    "lead_time_days": 10,
    "supplier_country": "BE",
    "supply_risk": "LOW",
    "source_type": "mock",
    "confidence_score": 0.82,
    "extraction_notes": "INEOS Antwerp not Hormuz-exposed. Different polymer family — Agnes must flag: requires line changeover if used."
  },
  {
    "id": "bio_pp_trellis_2026-04",
    "name": "Braskem Green PP",
    "supplier": "Braskem",
    "polymer_family": "BIO_PP",
    "grade_designation": "SEB27F",
    "is_recycled": false,
    "is_bio_based": true,
    "melt_flow_index_g10min": 10.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 33.0,
    "density_g_cm3": 0.900,
    "vicat_softening_temp_c": 147.0,
    "eu_food_contact": true,
    "reach_compliant": true,
    "certifications": ["ISCC", "ISO 9001", "Bonsucro"],
    "price_eur_per_kg": 2.20,
    "price_region": "EU_WEST",
    "price_date": "2026-04-17",
    "price_type": "list",
    "lead_time_days": 45,
    "supplier_country": "BR",
    "supply_risk": "MEDIUM",
    "source_type": "mock",
    "confidence_score": 0.75,
    "extraction_notes": "Sugar-cane based. Identical processing to fossil PP. Premium price but sustainability story for brand marketing."
  },
  {
    "id": "lotte_pp_hi500_2026-04",
    "name": "Lotte Chemical TITAN PP HI500",
    "supplier": "Lotte Chemical",
    "polymer_family": "PP",
    "grade_designation": "HI500",
    "is_recycled": false,
    "melt_flow_index_g10min": 10.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 36.0,
    "density_g_cm3": 0.900,
    "vicat_softening_temp_c": 154.0,
    "eu_food_contact": false,
    "reach_compliant": true,
    "price_eur_per_kg": 1.45,
    "price_region": "ASIA",
    "price_date": "2026-04-17",
    "price_type": "estimated",
    "lead_time_days": 70,
    "supplier_country": "KR",
    "supply_risk": "MEDIUM",
    "source_type": "mock",
    "confidence_score": 0.65,
    "extraction_notes": "No EU food contact confirmation. Lead time 70d unacceptable for summer peak. Agnes should rank last. Good for showing scoring handles bad candidates correctly."
  },
  {
    "id": "us_pp_formosa_2026-04",
    "name": "Formosa Plastics PP 4012",
    "supplier": "Formosa Plastics USA",
    "polymer_family": "PP",
    "grade_designation": "4012",
    "is_recycled": false,
    "melt_flow_index_g10min": 12.0,
    "mfi_test_conditions": "230°C/2.16kg",
    "tensile_strength_mpa": 34.5,
    "density_g_cm3": 0.900,
    "vicat_softening_temp_c": 151.0,
    "eu_food_contact": true,
    "reach_compliant": false,
    "price_eur_per_kg": 1.72,
    "price_region": "NORTH_AMERICA",
    "price_date": "2026-04-17",
    "price_type": "spot",
    "lead_time_days": 42,
    "supplier_country": "US",
    "supply_risk": "LOW",
    "source_type": "mock",
    "confidence_score": 0.72,
    "extraction_notes": "REACH compliance not confirmed — EU import may face regulatory issues. Good price but Agnes must flag compliance gap."
  }
]
```

### `data/mock/supplier_prices.json`

```json
{
  "meta": {
    "source": "plasticportal.eu + ICIS estimates",
    "region": "Central Europe",
    "date": "2026-04-17",
    "crisis_context": "Middle East conflict, Strait of Hormuz disruption, 38% PP price surge since Feb 2026"
  },
  "prices": {
    "PP_homo_spot":        {"eur_per_kg": 1.85, "change_pct_mom": 28.0},
    "PP_copo_spot":        {"eur_per_kg": 1.90, "change_pct_mom": 30.0},
    "PP_random_copo_spot": {"eur_per_kg": 1.73, "change_pct_mom": 23.4},
    "rPP_food_grade_est":  {"eur_per_kg": 1.61, "change_pct_mom": 5.0, "note": "Recycled — not Hormuz-exposed"},
    "HDPE_film_spot":      {"eur_per_kg": 1.58, "change_pct_mom": 18.0},
    "LLDPE_spot":          {"eur_per_kg": 1.62, "change_pct_mom": 20.0},
    "LDPE_spot":           {"eur_per_kg": 1.68, "change_pct_mom": 22.0},
    "PET_bottle_spot":     {"eur_per_kg": 1.12, "change_pct_mom": 14.0},
    "BIO_PP_list":         {"eur_per_kg": 2.20, "change_pct_mom": 2.0,  "note": "Bio-based — sugar cane, not petrochem exposed"}
  },
  "pre_crisis_baseline": {
    "PP_random_copo": 1.40,
    "HDPE_film":      1.34,
    "PET_bottle":     0.98
  }
}
```

---

## 8. Required Python Packages (data layer only)

Add to `requirements.txt`:

```
# Core
pydantic>=2.0
python-dotenv

# HTTP
httpx>=0.27
playwright>=1.43        # only needed if JS scraping required

# PDF extraction
pymupdf>=1.24           # fitz — primary
pdfplumber>=0.11        # fallback for text-heavy PDFs

# HTML parsing
beautifulsoup4>=4.12
lxml>=5.0

# Data
pandas>=2.0             # for price table parsing
python-dateutil

# OCR (if scanned PDFs appear)
pytesseract             # requires tesseract binary: apt install tesseract-ocr
Pillow>=10.0
```

---

## 9. Environment Variables

`.env.example` — data layer keys:

```bash
# Scraping behavior
SCRAPER_CACHE_MAX_AGE_HOURS=4     # Use cached raw/ files if younger than this
SCRAPER_REQUEST_DELAY_S=1.5       # Politeness delay between requests
SCRAPER_TIMEOUT_S=15

# Fallback
USE_MOCK_ON_SCRAPER_FAILURE=true  # ALWAYS true during demo

# FX rate for price normalization (update day-of if USD sources used)
FX_USD_TO_EUR=0.92

# Paths (override if needed)
RAW_DATA_DIR=data/raw
PROCESSED_DATA_DIR=data/processed
MOCK_DATA_DIR=data/mock
```

---

## 10. What the Ingestion Agent Must Log

Every run of `ingestion_agent.py` must write `data/processed/run_log.json`:

```json
{
  "run_at": "2026-04-17T10:00:00Z",
  "materials_scraped": 8,
  "materials_validated": 8,
  "materials_failed_validation": 0,
  "sources_used": ["mock", "plasticportal_cache"],
  "scraper_errors": [],
  "merges_performed": [],
  "warnings": [
    "Veolia rPP price is estimated — confidence 0.80",
    "Formosa REACH compliance not confirmed"
  ],
  "fallback_used": false
}
```

---

## 11. Demo Readiness Checklist

Run this before the live presentation:

```bash
# 1. Verify mock data loads without errors
python -c "
from agents.ingestion_agent import load_materials
mats = load_materials(use_cache=False, fallback_to_mock=True)
print(f'Loaded {len(mats)} materials')
assert len(mats) >= 6, 'Need at least 6 candidates for scoring demo'
print('All MaterialRecord validations passed')
"

# 2. Verify disruption event loads
python -c "
import json
from pathlib import Path
evt = json.loads(Path('data/mock/disruption_event.json').read_text())
print(f'Disruption: {evt[\"disruption_cause\"]}')
print(f'Severity: {evt[\"severity\"]}')
"

# 3. Verify prices are loaded and crisis-level
python -c "
import json
from pathlib import Path
prices = json.loads(Path('data/mock/supplier_prices.json').read_text())
pp = prices['prices']['PP_random_copo_spot']['eur_per_kg']
assert pp > 1.50, f'PP price {pp} too low — update mock data'
print(f'PP spot price: {pp} EUR/kg — crisis level confirmed')
"

# 4. Run full pipeline smoke test
python demo/scenario.py --dry-run
```

---

## 12. What NOT to Do

- **Never hardcode prices in scoring logic.** Prices live in `data/` only.
- **Never write to `data/raw/` from anywhere except scrapers.**
- **Never let the scoring engine receive a dict.** Always pass `MaterialRecord` objects.
- **Never silently swallow extraction errors.** Log with `WARNING` level and set `confidence_score` lower.
- **Never skip the validator.** Even mock data must pass `MaterialRecord(**data)` instantiation.
- **Never store credentials in `.env` files that get committed.** The `.gitignore` must include `.env`.