# Makeathon26 Spherecast

Material substitution system with crawling, scoring, and UI/API integration.

## Quick Start

Run both backend API and frontend server:

```bash
python start_ui.py
```

- API: `http://127.0.0.1:8001`
- Frontend: `http://127.0.0.1:8000`

Detailed run instructions: [`START.md`](START.md)

## Project Layout

- `src/ui` - FastAPI endpoints and frontend app
- `src/scoring` - knockout + weighted scoring pipeline
- `src/crawling` - extraction and scoring CSV transforms
- `shared` - shared schemas and constants
- `tests` - scoring/ui/crawling tests
- `docs` - architecture and module documentation
- `_archive` - legacy root scripts and old outputs kept for traceability

## Notes

- Runtime scoring data is generated in `data/scoring_capsuline_materials.csv` from `data/extracted_capsuline_products.csv` when required by the UI orchestrator.
- Legacy helper scripts remain in `src/database/legacy`; archived one-off root scripts were moved to `_archive/root_scripts`.
