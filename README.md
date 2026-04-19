# Spherecast

Spherecast is a material substitution demo system built for Makeathon: it ingests supplier data, converts it into a scoring contract, ranks substitutes with a multi-dimensional scoring pipeline, and exposes results in a UI.

## Problem & Goal

Procurement teams need fast and explainable alternatives when a material is unavailable, too expensive, or non-compliant.  
Our goal was to build an end-to-end workflow that:

- evaluates candidates with transparent scoring,
- highlights hard constraints (knockout rules),
- shows actionable contact information for supplier follow-up.

## General Approach

We implemented a CSV-first architecture so we could iterate quickly and keep a clear data contract across crawling, scoring, and UI.

1. Supplier/extracted data is stored in `data/extracted_capsuline_products.csv`.
2. A transformer maps extracted rows into the scoring CSV contract.
3. The API orchestrator loads runtime scoring data (`data/scoring_capsuline_materials.csv`) and falls back to test data if needed.
4. The scoring pipeline applies:
   - knockout filtering (hard exclusions),
   - 5D scoring (spec, compliance, price, lead time, quality),
   - confidence/uncertainty and explanation generation.
5. The frontend displays ranked candidates, rejected candidates, and detailed explanations.

## Architecture (ASCII)

```text
                   +----------------------------------+
                   | data/extracted_capsuline_*.csv  |
                   +----------------+-----------------+
                                    |
                                    v
                    +-------------------------------+
                    | scoring_csv_transform.py      |
                    | -> scoring_capsuline_*.csv    |
                    +---------------+---------------+
                                    |
                                    v
 +---------------------+   +-------------------------------+   +----------------------+
 | FastAPI /api/csv/*  +-->+ orchestrator.py               +-->+ scoring.pipeline     |
 | search + score      |   | runtime CSV resolve/refresh   |   | KO + 5D + explain    |
 +----------+----------+   +---------------+---------------+   +----------+-----------+
            |                              |                              |
            v                              v                              v
   +------------------+          +-------------------+           +----------------------+
   | frontend (JS UI) |<---------+ serialized result +-----------+ top/rejected + meta |
   +------------------+          +-------------------+           +----------------------+
```

## Repository Structure (ASCII)

```text
Makeathon26_Spherecast/
├── shared/                  # shared schemas/constants
├── src/
│   ├── crawling/            # extract + transform utilities
│   ├── scoring/             # knockout + 5D scoring pipeline
│   └── ui/                  # FastAPI + frontend components
├── data/                    # extracted + runtime scoring CSVs
├── tests/                   # scoring/crawling/ui tests
├── START.md                 # run instructions
└── README.md
```

## New Contact & Allergen Transparency Features

We added explicit supplier contact visibility in the expanded candidate explanation:

- `For more information, contact sales: <email>`  
  Fallback: `No email for the seller`
- `Website: <website>`  
  Fallback: `No website for the seller`

Contact values are read from CSV with robust header support (email variants + website/source URL fallback).

We also added allergen transparency in detailed explanations:

- show selected prohibited allergens,
- show detected `contains` / `may contain` hits when available,
- if allergen data is missing, show: `Contact seller for better information`.

This avoids false confidence when users selected prohibited allergens but source data is incomplete.

## What Worked

- Stable scoring core with clear KO + ranked outputs.
- Good modular separation between transformation, scoring, and UI rendering.
- Runtime CSV refresh pattern works well for rapid demo iteration.
- Explanation panel became actionable with direct supplier contact context.

## What Didn’t Work (or is incomplete)

- Supplier crawling coverage is still uneven across sources.
- Some flows depend on external services/network (embedding backend), causing skipped tests in offline/unreliable conditions.
- Data quality for allergens and some supplier metadata is inconsistent, so fallbacks are still necessary.

## How We Would Improve the Submission

1. Build automated mailbox ingestion (AWS inbox -> attachment parser -> transform -> runtime CSV update).
2. Add supplier-specific templates for parsing PDFs/price sheets reliably.
3. Add stronger data validation and anomaly checks before merging new price sheets.
4. Expand observability (ingestion status, parse failures, stale data alerts).
5. Increase end-to-end tests for ingestion + UI traceability.

## Quick Start

Run both backend API and frontend:

```bash
python start_ui.py
```

- API: `http://127.0.0.1:8001`
- Frontend: `http://127.0.0.1:8000`

Detailed instructions: [START.md](START.md)
