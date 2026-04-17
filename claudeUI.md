# CLAUDE.md — UI Modul

## Überblick

Dieses Modul ist verantwortlich für die Darstellung der Scoring-Ergebnisse. Es nimmt die ScoringResults vom Scoring-Modul entgegen und präsentiert sie dem User über eine API und ein Frontend.

## Input und Output

### Input (vom Scoring-Modul)

```python
ScoringResult(
    original: CrawledMaterial,
    top_candidates: list[ScoredCandidate],
    rejected: list[RejectedCandidate],
    metadata: ScoringMetadata
)
```

### Output

- REST API Responses (JSON)
- Frontend-Visualisierung (React/HTML)
- Demo-Interface für Makeathon

## Dateistruktur

```
src/ui/
├── CLAUDE.md                  # Diese Datei
├── __init__.py                # Exports
│
├── api/                       # BACKEND
│   ├── __init__.py
│   ├── main.py                # FastAPI App
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── search.py          # POST /search
│   │   ├── results.py         # GET /results/{id}
│   │   └── config.py          # GET/PUT /config (Gewichte)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py        # Request Models
│   │   └── responses.py       # Response Models
│   └── services/
│       ├── __init__.py
│       └── orchestrator.py    # Verbindet Crawling + Scoring
│
├── frontend/                  # FRONTEND
│   ├── index.html
│   ├── styles/
│   │   └── main.css
│   ├── components/
│   │   ├── SearchForm.js      # Eingabeformular
│   │   ├── ResultsList.js     # Top 5 Liste
│   │   ├── CandidateCard.js   # Einzelner Kandidat
│   │   ├── ScoreBreakdown.js  # 5D Score Visualisierung
│   │   ├── ComparisonView.js  # Original vs Kandidat
│   │   ├── WeightSliders.js   # Gewichte anpassen (Demo)
│   │   └── RejectedList.js    # K.O.-gefilterte anzeigen
│   └── utils/
│       └── api.js             # API Client
│
└── demo/                      # MAKEATHON DEMO
    ├── demo_runner.py         # Demo-Skript
    └── sample_queries.json    # Vordefinierte Beispiele
```

## Architektur

```
SCORING RESULT                                          
(ScoringResult)                  
            │                                       
            ▼                                       
┌───────────────────────────────────────────────────────────────────┐
│ API LAYER (api/)                                                  │
│                                                                   │
│ FastAPI Server                                                    │
│ • POST /search         → Neue Suche starten                       │
│ • GET /results/{id}    → Ergebnisse abrufen                       │
│ • GET /config          → Aktuelle Gewichte                        │
│ • PUT /config          → Gewichte anpassen                        │
│ • WebSocket /ws        → Live Updates (optional)                  │
│                                                                   │
│ Output: JSON Responses                                            │
└───────────────────────────────────────────────────────────────────┘
            │                                       
            ▼                                       
┌───────────────────────────────────────────────────────────────────┐
│ FRONTEND LAYER (frontend/)                                        │
│                                                                   │
│ • Suchformular                                                    │
│ • Ergebnis-Liste (Top 5)                                          │
│ • Detail-Ansicht pro Kandidat                                     │
│ • Score-Breakdown Visualisierung                                  │
│ • Vergleichs-Ansicht                                              │
│ • Gewichte-Slider (Demo)                                          │
│                                                                   │
│ Output: Interaktive UI                                            │
└───────────────────────────────────────────────────────────────────┘
            │                                       
            ▼                                       
USER SIEHT: Ranking mit Empfehlungen                                
```

## API Endpoints

### POST /search

Startet eine neue Material-Suche.

Request:
```python
@dataclass
class SearchRequest:
    original_material: MaterialInput       # Was soll ersetzt werden
    search_criteria: SearchCriteria        # Suchparameter
    user_requirements: UserRequirements    # K.O.-Kriterien
    weights: dict[str, float] | None       # Custom Gewichte (optional)
    top_n: int = 5                         # Anzahl Ergebnisse
```

```json
{
    "original_material": {
        "name": "Aluminium 6061-T6",
        "category": "metals",
        "properties": {
            "zugfestigkeit": {"value": 310, "unit": "MPa"},
            "dichte": {"value": 2.7, "unit": "g/cm³"}
        },
        "certifications": ["RoHS", "REACH"]
    },
    "search_criteria": {
        "category": "metals",
        "application": "structural",
        "max_results": 50
    },
    "user_requirements": {
        "max_quantity": 500,
        "destination_country": "DE",
        "critical_certs": ["RoHS"],
        "max_lead_time_days": 60,
        "max_price_multiplier": 2.0
    },
    "weights": null,
    "top_n": 5
}
```

Response:
```json
{
    "search_id": "search_abc123",
    "status": "completed",
    "original": {
        "id": "orig_001",
        "name": "Aluminium 6061-T6",
        "properties": {...},
        "certifications": [...],
        "price": {"value": 3.50, "unit": "€/kg"},
        "lead_time": {"days": 14, "reliability": 0.92}
    },
    "top_candidates": [
        {
            "rank": 1,
            "kandidat": {
                "id": "cand_001",
                "name": "Aluminium 7075-T6",
                "properties": {...},
                "certifications": [...],
                "price": {"value": 4.20, "unit": "€/kg"},
                "lead_time": {"days": 21, "reliability": 0.88}
            },
            "composite_score": 0.847,
            "scores": {
                "spec": 0.92,
                "compliance": 1.0,
                "price": 0.64,
                "lead_time": 0.67,
                "quality": 0.78
            },
            "explanation": {
                "summary": "Gute Alternative",
                "recommendation": "Empfohlen",
                "strengths": [
                    "Technisch sehr ähnlich",
                    "Alle Zertifikate vorhanden"
                ],
                "weaknesses": [
                    "Teurer (+20%)",
                    "Längere Lieferzeit (+7 Tage)"
                ],
                "risks": []
            }
        }
    ],
    "rejected_count": 12,
    "metadata": {
        "total_candidates": 47,
        "passed_knockout": 35,
        "weights_used": {
            "spec": 0.40,
            "compliance": 0.25,
            "price": 0.15,
            "lead_time": 0.10,
            "quality": 0.10
        },
        "processing_time_ms": 1234
    }
}
```

### GET /results/{search_id}

Ruft Ergebnisse einer vorherigen Suche ab.

Response: Gleiches Format wie POST /search Response

### GET /results/{search_id}/rejected

Zeigt die K.O.-gefilterten Kandidaten.

Response:
```json
{
    "search_id": "search_abc123",
    "rejected": [
        {
            "kandidat": {
                "id": "rej_001",
                "name": "Stahl S235",
                "country_of_origin": "CN"
            },
            "reasons": [
                "MOQ (5000) > Max (500)",
                "Kritisches Zertifikat fehlt: FDA"
            ]
        }
    ],
    "total_rejected": 12
}
```

### GET /config

Aktuelle Scoring-Konfiguration abrufen.

Response:
```json
{
    "weights": {
        "spec": 0.40,
        "compliance": 0.25,
        "price": 0.15,
        "lead_time": 0.10,
        "quality": 0.10
    },
    "presets": {
        "default": {...},
        "cost_focused": {...},
        "availability_focused": {...},
        "quality_focused": {...}
    },
    "knockout_defaults": {
        "max_price_multiplier": 2.0,
        "max_lead_time_days": 90
    }
}
```

### PUT /config

Gewichte anpassen (für Demo).

Request:
```json
{
    "weights": {
        "spec": 0.30,
        "compliance": 0.25,
        "price": 0.10,
        "lead_time": 0.25,
        "quality": 0.10
    }
}
```

Response:
```json
{
    "status": "updated",
    "weights": {...},
    "message": "Weights updated. New searches will use these weights."
}
```

### POST /rescore/{search_id}

Re-Scoring mit neuen Gewichten (ohne neues Crawling).

Request:
```json
{
    "weights": {
        "spec": 0.30,
        "compliance": 0.20,
        "price": 0.35,
        "lead_time": 0.05,
        "quality": 0.10
    }
}
```

Response: Gleiches Format wie POST /search, aber mit neuen Scores

## API Implementation

Datei: api/main.py

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Spherecast Substitute Finder",
    description="Material Substitution Scoring API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes einbinden
from .routes import search, results, config
app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(results.router, prefix="/results", tags=["Results"])
app.include_router(config.router, prefix="/config", tags=["Config"])

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

Datei: api/routes/search.py

```python
from fastapi import APIRouter, BackgroundTasks
from ..models.requests import SearchRequest
from ..models.responses import SearchResponse
from ..services.orchestrator import run_search

router = APIRouter()

# In-Memory Store für Demo (Production: Redis/DB)
search_results = {}

@router.post("/", response_model=SearchResponse)
async def create_search(request: SearchRequest):
    """
    Startet eine neue Material-Suche.
    
    1. Crawling: Materialien von Agnes holen
    2. Scoring: 5D Bewertung durchführen
    3. Ergebnis speichern und zurückgeben
    """
    result = await run_search(
        original=request.original_material,
        criteria=request.search_criteria,
        requirements=request.user_requirements,
        weights=request.weights,
        top_n=request.top_n
    )
    
    search_results[result.search_id] = result
    
    return result
```

Datei: api/services/orchestrator.py

```python
from src.crawling import crawl_materials
from src.scoring import find_substitutes
from shared.schemas import ScoringResult
import uuid
import time

async def run_search(
    original,
    criteria,
    requirements,
    weights,
    top_n
) -> SearchResponse:
    """
    Orchestriert Crawling und Scoring.
    """
    start_time = time.time()
    search_id = f"search_{uuid.uuid4().hex[:8]}"
    
    # 1. Crawling
    candidates = crawl_materials(
        original=original,
        search_criteria=criteria,
        destination_country=requirements.destination_country
    )
    
    # 2. Scoring
    scoring_result = find_substitutes(
        original=original,
        candidates=candidates,
        user_requirements=requirements,
        weights=weights,
        top_n=top_n
    )
    
    processing_time = int((time.time() - start_time) * 1000)
    
    return SearchResponse(
        search_id=search_id,
        status="completed",
        original=scoring_result.original,
        top_candidates=scoring_result.top_candidates,
        rejected_count=len(scoring_result.rejected),
        metadata={
            **scoring_result.metadata,
            "processing_time_ms": processing_time
        }
    )
```

## Frontend Components

### SearchForm.js

Eingabeformular für die Material-Suche.

```javascript
// Funktionalität:
// - Material-Name eingeben oder aus Liste wählen
// - Kategorie wählen (Metalle, Kunststoffe, etc.)
// - Properties definieren (optional)
// - Zertifikat-Anforderungen setzen
// - User Requirements (MOQ, Max Lead Time, etc.)

// Events:
// - onSubmit → POST /search aufrufen
// - onReset → Formular zurücksetzen

// State:
// - formData: MaterialInput
// - isLoading: boolean
// - errors: ValidationErrors
```

### ResultsList.js

Zeigt die Top 5 Kandidaten als Liste.

```javascript
// Props:
// - candidates: ScoredCandidate[]
// - original: CrawledMaterial
// - onSelectCandidate: (id) => void

// Darstellung pro Kandidat:
// - Rank (1-5)
// - Name
// - Composite Score als Prozent und Balken
// - Mini Score-Breakdown (5 kleine Balken)
// - Recommendation Badge (Empfohlen/Bedingt/Nicht empfohlen)
// - Strengths/Weaknesses Icons

// Interaktion:
// - Click → Detail-Ansicht öffnen
// - Hover → Quick-Info Tooltip
```

### CandidateCard.js

Detail-Ansicht eines einzelnen Kandidaten.

```javascript
// Props:
// - candidate: ScoredCandidate
// - original: CrawledMaterial
// - onClose: () => void

// Sections:
// 1. Header
//    - Name, Supplier, Country
//    - Composite Score groß
//    - Recommendation

// 2. Score Breakdown
//    - ScoreBreakdown Component einbinden

// 3. Comparison
//    - ComparisonView Component einbinden

// 4. Explanation
//    - Strengths (grün)
//    - Weaknesses (rot)
//    - Risks (orange)

// 5. Details
//    - Alle Properties
//    - Alle Certifications
//    - Pricing Details
//    - Supplier Info
```

### ScoreBreakdown.js

Visualisiert die 5 Dimension-Scores.

```javascript
// Props:
// - scores: {spec, compliance, price, lead_time, quality}
// - weights: {spec, compliance, price, lead_time, quality}
// - showWeights: boolean

// Darstellung:
// - 5 horizontale Balken
// - Jeder Balken zeigt:
//   - Dimension-Name
//   - Score als Prozent
//   - Farbiger Balken (grün > 0.8, gelb > 0.5, rot < 0.5)
//   - Gewicht in Klammern wenn showWeights=true

// Layout:
// ┌────────────────────────────────────────┐
// │ Spec Similarity (40%)                  │
// │ ████████████████████░░░░░░░░ 92%       │
// │                                        │
// │ Compliance (25%)                       │
// │ █████████████████████████████ 100%     │
// │                                        │
// │ Price Delta (15%)                      │
// │ ████████████░░░░░░░░░░░░░░░░ 64%       │
// │                                        │
// │ Lead Time (10%)                        │
// │ █████████████░░░░░░░░░░░░░░░ 67%       │
// │                                        │
// │ Quality Signals (10%)                  │
// │ ███████████████░░░░░░░░░░░░░ 78%       │
// └────────────────────────────────────────┘
```

### ComparisonView.js

Vergleicht Original mit Kandidat.

```javascript
// Props:
// - original: CrawledMaterial
// - kandidat: CrawledMaterial

// Darstellung als Tabelle:
// ┌──────────────────┬────────────┬────────────┬──────────┐
// │ Property         │ Original   │ Kandidat   │ Diff     │
// ├──────────────────┼────────────┼────────────┼──────────┤
// │ Zugfestigkeit    │ 310 MPa    │ 572 MPa    │ +84% ▲   │
// │ Dichte           │ 2.7 g/cm³  │ 2.81 g/cm³ │ +4%      │
// │ Preis            │ 3.50 €/kg  │ 4.20 €/kg  │ +20% ▼   │
// │ Lead Time        │ 14 Tage    │ 21 Tage    │ +7 ▼     │
// │ Zertifikate      │ 3          │ 3          │ =        │
// └──────────────────┴────────────┴────────────┴──────────┘

// Farbcodierung:
// - Grün (▲): Kandidat besser
// - Rot (▼): Kandidat schlechter
// - Grau (=): Gleich/Neutral
```

### WeightSliders.js

Demo-Feature: Gewichte live anpassen.

```javascript
// Props:
// - weights: {spec, compliance, price, lead_time, quality}
// - onChange: (newWeights) => void
// - onApply: () => void
// - presets: {name: weights}[]

// Darstellung:
// ┌────────────────────────────────────────┐
// │ Gewichte anpassen                      │
// │                                        │
// │ Spec Similarity                        │
// │ ○──────────●──────────○  40%           │
// │                                        │
// │ Compliance                             │
// │ ○──────●──────────────○  25%           │
// │                                        │
// │ Price Delta                            │
// │ ○────●────────────────○  15%           │
// │                                        │
// │ Lead Time                              │
// │ ○──●──────────────────○  10%           │
// │                                        │
// │ Quality Signals                        │
// │ ○──●──────────────────○  10%           │
// │                                        │
// │ ┌─────────┐ ┌─────────┐ ┌──────────┐   │
// │ │ Default │ │ Cost    │ │ Avail.   │   │
// │ └─────────┘ └─────────┘ └──────────┘   │
// │                                        │
// │        [ Neu berechnen ]               │
// └────────────────────────────────────────┘

// Interaktion:
// - Slider bewegen → onChange
// - Preset klicken → Alle Slider anpassen
// - "Neu berechnen" → onApply → POST /rescore
```

### RejectedList.js

Zeigt die K.O.-gefilterten Kandidaten.

```javascript
// Props:
// - rejected: RejectedCandidate[]
// - onShowDetails: (id) => void

// Darstellung:
// ┌────────────────────────────────────────┐
// │ 12 Kandidaten aussortiert              │
// │                                        │
// │ ┌────────────────────────────────────┐ │
// │ │ ✗ Stahl S235                       │ │
// │ │   • MOQ (5000) > Max (500)         │ │
// │ │   • FDA fehlt                      │ │
// │ └────────────────────────────────────┘ │
// │                                        │
// │ ┌────────────────────────────────────┐ │
// │ │ ✗ Kupfer C11000                    │ │
// │ │   • Herkunft CN gesperrt           │ │
// │ └────────────────────────────────────┘ │
// │                                        │
// │         [ Mehr anzeigen ]              │
// └────────────────────────────────────────┘
```

## Frontend State Management

```javascript
// Zentraler App State

const initialState = {
    // Search
    searchForm: {
        originalMaterial: null,
        searchCriteria: {},
        userRequirements: {},
        isLoading: false,
        error: null
    },
    
    // Results
    currentSearch: {
        searchId: null,
        original: null,
        topCandidates: [],
        rejectedCount: 0,
        metadata: {}
    },
    
    // Selected Candidate
    selectedCandidate: null,
    
    // Config
    weights: {
        spec: 0.40,
        compliance: 0.25,
        price: 0.15,
        lead_time: 0.10,
        quality: 0.10
    },
    
    // UI State
    ui: {
        showRejected: false,
        showWeightSliders: false,
        compareMode: false
    }
};

// Actions
const actions = {
    SUBMIT_SEARCH: 'search/submit',
    SEARCH_SUCCESS: 'search/success',
    SEARCH_ERROR: 'search/error',
    
    SELECT_CANDIDATE: 'candidate/select',
    DESELECT_CANDIDATE: 'candidate/deselect',
    
    UPDATE_WEIGHTS: 'config/updateWeights',
    APPLY_PRESET: 'config/applyPreset',
    RESCORE: 'config/rescore',
    
    TOGGLE_REJECTED: 'ui/toggleRejected',
    TOGGLE_WEIGHTS: 'ui/toggleWeights'
};
```

## API Client

Datei: frontend/utils/api.js

```javascript
const API_BASE = process.env.API_URL || 'http://localhost:8000';

export const api = {
    async search(request) {
        const response = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(request)
        });
        
        if (!response.ok) {
            throw new Error(`Search failed: ${response.statusText}`);
        }
        
        return response.json();
    },
    
    async getResults(searchId) {
        const response = await fetch(`${API_BASE}/results/${searchId}`);
        
        if (!response.ok) {
            throw new Error(`Failed to get results: ${response.statusText}`);
        }
        
        return response.json();
    },
    
    async getRejected(searchId) {
        const response = await fetch(`${API_BASE}/results/${searchId}/rejected`);
        return response.json();
    },
    
    async getConfig() {
        const response = await fetch(`${API_BASE}/config`);
        return response.json();
    },
    
    async updateConfig(weights) {
        const response = await fetch(`${API_BASE}/config`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({weights})
        });
        return response.json();
    },
    
    async rescore(searchId, weights) {
        const response = await fetch(`${API_BASE}/rescore/${searchId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({weights})
        });
        return response.json();
    }
};
```

## Demo-Modus

Datei: demo/demo_runner.py

### Vordefinierte Beispiele

```python
DEMO_SCENARIOS = [
    {
        "name": "Aluminium Substitution",
        "description": "Ersatz für Aluminium 6061-T6 finden",
        "original": {
            "name": "Aluminium 6061-T6",
            "category": "metals",
            "properties": {
                "zugfestigkeit": {"value": 310, "unit": "MPa"},
                "dichte": {"value": 2.7, "unit": "g/cm³"}
            },
            "certifications": ["RoHS", "REACH"],
            "price": {"value": 3.50, "unit": "€/kg"}
        },
        "requirements": {
            "max_quantity": 500,
            "critical_certs": ["RoHS"],
            "destination_country": "DE"
        }
    },
    {
        "name": "Kunststoff für Lebensmittel",
        "description": "FDA-konformer Kunststoff für Verpackung",
        "original": {
            "name": "PET Food Grade",
            "category": "polymers",
            "properties": {
                "zugfestigkeit": {"value": 55, "unit": "MPa"},
                "schmelzpunkt": {"value": 260, "unit": "°C"}
            },
            "certifications": ["FDA", "EU-10/2011"],
            "price": {"value": 1.80, "unit": "€/kg"}
        },
        "requirements": {
            "critical_certs": ["FDA"],
            "max_price_multiplier": 1.5
        }
    },
    {
        "name": "Schnelle Verfügbarkeit",
        "description": "Zeigt Gewichtung auf Lead Time",
        "original": {...},
        "requirements": {...},
        "weights": {
            "spec": 0.30,
            "compliance": 0.20,
            "price": 0.10,
            "lead_time": 0.30,
            "quality": 0.10
        }
    }
]
```

### Demo-Features für Makeathon

1. One-Click Demo Scenarios
   - Vordefinierte Szenarien laden
   - Sofort Ergebnisse zeigen

2. Live Gewichte-Anpassung
   - Slider bewegen
   - Sofort neu berechnen
   - Ranking ändert sich live

3. Vergleichs-Modus
   - Original und Kandidat nebeneinander
   - Property-by-Property Vergleich
   - Visuelle Unterschiede

4. K.O.-Filter Erklärung
   - Zeigen warum Materialien rausgeflogen sind
   - Transparenz über den Prozess

5. Score-Erklärung
   - Hover über Score → Formel zeigen
   - Verstehen wie der Score zustande kommt

## Styling

### Farbschema

```css
:root {
    /* Primary */
    --color-primary: #2563eb;
    --color-primary-light: #3b82f6;
    --color-primary-dark: #1d4ed8;
    
    /* Scores */
    --color-score-excellent: #22c55e;  /* > 0.8 */
    --color-score-good: #84cc16;       /* > 0.7 */
    --color-score-medium: #eab308;     /* > 0.5 */
    --color-score-poor: #f97316;       /* > 0.3 */
    --color-score-bad: #ef4444;        /* < 0.3 */
    
    /* Recommendations */
    --color-recommended: #22c55e;
    --color-conditional: #eab308;
    --color-not-recommended: #ef4444;
    
    /* Backgrounds */
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #f1f5f9;
    
    /* Text */
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    
    /* Borders */
    --border-color: #e2e8f0;
    --border-radius: 8px;
}
```

### Score-Farben Funktion

```javascript
function getScoreColor(score) {
    if (score >= 0.8) return 'var(--color-score-excellent)';
    if (score >= 0.7) return 'var(--color-score-good)';
    if (score >= 0.5) return 'var(--color-score-medium)';
    if (score >= 0.3) return 'var(--color-score-poor)';
    return 'var(--color-score-bad)';
}

function getRecommendationColor(recommendation) {
    switch (recommendation) {
        case 'Empfohlen': return 'var(--color-recommended)';
        case 'Bedingt empfohlen': return 'var(--color-conditional)';
        default: return 'var(--color-not-recommended)';
    }
}
```

## Testing

### Teststruktur

```
tests/ui/
├── api/
│   ├── test_search.py
│   ├── test_results.py
│   └── test_config.py
├── frontend/
│   ├── test_components.js
│   └── test_api_client.js
└── integration/
    └── test_full_flow.py
```

### API Tests

```python
# tests/ui/api/test_search.py

def test_search_success(client, mock_orchestrator):
    response = client.post("/search", json={
        "original_material": {...},
        "search_criteria": {...},
        "user_requirements": {...}
    })
    
    assert response.status_code == 200
    assert "search_id" in response.json()
    assert len(response.json()["top_candidates"]) <= 5

def test_search_invalid_input(client):
    response = client.post("/search", json={})
    assert response.status_code == 422

def test_rescore_changes_ranking(client, mock_search_result):
    # Erst mit Default-Gewichten
    result1 = client.post("/search", json={...}).json()
    
    # Dann mit Price-fokussierten Gewichten
    result2 = client.post(f"/rescore/{result1['search_id']}", json={
        "weights": {"spec": 0.2, "compliance": 0.2, "price": 0.4, ...}
    }).json()
    
    # Ranking sollte sich geändert haben
    assert result1["top_candidates"][0]["kandidat"]["id"] != \
           result2["top_candidates"][0]["kandidat"]["id"]
```

## Error Handling

### API Errors

```python
from fastapi import HTTPException

class SearchError(Exception):
    pass

class CrawlingError(SearchError):
    pass

class ScoringError(SearchError):
    pass

@app.exception_handler(SearchError)
async def search_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "search_failed",
            "message": str(exc),
            "search_id": getattr(exc, 'search_id', None)
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "request_error",
            "message": exc.detail
        }
    )
```

### Frontend Error Handling

```javascript
// Zentrales Error Handling

async function handleApiCall(apiCall, errorMessage) {
    try {
        return await apiCall();
    } catch (error) {
        console.error(errorMessage, error);
        
        // User-freundliche Fehlermeldung
        showErrorNotification({
            title: 'Fehler',
            message: errorMessage,
            details: error.message
        });
        
        throw error;
    }
}

// Verwendung
const results = await handleApiCall(
    () => api.search(searchRequest),
    'Suche konnte nicht durchgeführt werden'
);
```

## Performance

### API Caching

```python
from functools import lru_cache
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

# Config cachen (ändert sich selten)
@lru_cache(maxsize=1)
def get_default_config():
    return load_config_from_file()

# Search Results cachen (für Re-Scoring)
@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost")
    FastAPICache.init(RedisBackend(redis), prefix="spherecast")
```

### Frontend Performance

```javascript
// Lazy Loading für Detail-Komponenten
const CandidateCard = React.lazy(() => import('./CandidateCard'));
const ComparisonView = React.lazy(() => import('./ComparisonView'));

// Memoization für teure Berechnungen
const memoizedScoreBreakdown = useMemo(
    () => calculateBreakdown(scores, weights),
    [scores, weights]
);

// Debounce für Slider
const debouncedWeightUpdate = useMemo(
    () => debounce(onWeightChange, 300),
    [onWeightChange]
);
```

## Deployment

### Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY shared/ shared/

EXPOSE 8000

CMD ["uvicorn", "src.ui.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - AGNES_API_KEY=${AGNES_API_KEY}
    
  frontend:
    build: ./src/ui/frontend
    ports:
      - "3000:3000"
    depends_on:
      - api
```

## Dependencies

### Backend
```
fastapi
uvicorn
pydantic
python-multipart
aioredis
fastapi-cache2
```

### Frontend
```
react
react-dom
recharts          # Für Score-Visualisierung
tailwindcss       # Styling
axios             # API Calls
```