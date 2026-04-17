# CLAUDE.md — Scoring Modul

## Überblick

Dieses Modul ist verantwortlich für das 5-dimensionale Scoring-System zur Bewertung von Material-Substituten. Es nimmt normalisierte Materialdaten vom Crawling-Modul entgegen und liefert ein Ranking mit Explanations, Evidence Trails und Uncertainty-Bewertungen an das UI-Modul.

### Challenge-Alignment

Dieses Modul adressiert folgende Challenge-Anforderungen:
- **Functionally interchangeable components**: Spec Similarity
- **Quality and compliance requirements**: Compliance Score + K.O.-Filter
- **Explainable sourcing recommendation**: Evidence Trail + Explanation Generator
- **Cost, lead time, practical feasibility**: Price Delta, Lead Time, Quality Signals
- **Uncertainty, evidence quality, tradeoffs**: Confidence Scores + Evidence Sources
- **Supplier consolidation**: BOM-Konsolidierungs-Layer

## Input und Output

### Input (vom Crawling-Modul)

```python
original: CrawledMaterial           # Das zu ersetzende Material
candidates: list[CrawledMaterial]   # Alle potenziellen Ersatzmaterialien
user_requirements: UserRequirements # K.O.-Kriterien und Präferenzen
bom_context: BOMContext | None      # Optional: Für BOM-Konsolidierung
```

### Output (für UI-Modul)

```python
ScoringResult(
    original: CrawledMaterial,
    top_candidates: list[ScoredCandidate],  # Top 5 mit Scores, Explanations, Evidence
    rejected: list[RejectedCandidate],       # K.O.-gefilterte mit Gründen
    metadata: ScoringMetadata,               # Weights, counts, config
    consolidation: ConsolidationResult | None # BOM-Konsolidierungs-Empfehlung
)
```

## Dateistruktur

```
src/scoring/
├── CLAUDE.md              # Diese Datei
├── __init__.py            # Exports
│
├── knockout.py            # Stufe 0: K.O.-Filter
├── spec_similarity.py     # Dimension 1: Spec Similarity (40%)
├── compliance.py          # Dimension 2: Compliance Match (25%)
├── price_delta.py         # Dimension 3: Price Delta (15%)
├── lead_time.py           # Dimension 4: Lead Time (10%)
├── quality_signals.py     # Dimension 5: Quality Signals (10%)
├── composite.py           # Composite Score Berechnung
│
├── evidence.py            # Evidence Trail Tracking
├── uncertainty.py         # Uncertainty/Confidence Berechnung
├── consolidation.py       # BOM-Konsolidierungs-Layer
├── explanation.py         # Explanation Generator
│
└── pipeline.py            # Orchestrierung der gesamten Pipeline
```

## Pipeline-Architektur

```
INPUT: list[CrawledMaterial] + BOMContext (optional)
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ STUFE 0: K.O.-FILTER (knockout.py)                                │
│                                                                   │
│ Harte Ausschlusskriterien BEVOR gescored wird:                    │
│ • MOQ > User's max quantity              → RAUS                   │
│ • Country of Origin auf Blacklist        → RAUS                   │
│ • Critical Certification fehlt           → RAUS                   │
│ • Lead Time > absolutes Maximum          → RAUS                   │
│ • Preis > absolutes Maximum              → RAUS                   │
│                                                                   │
│ + Evidence: Grund für K.O. mit Quellenangabe                      │
│                                                                   │
│ Output: max. 15 Kandidaten                                        │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ STUFE 1: 5D SCORING + EVIDENCE COLLECTION                         │
│                                                                   │
│ Für jeden Kandidaten:                                             │
│ • Alle 5 Dimensionen berechnen                                    │
│ • Evidence Trail pro Dimension sammeln                            │
│ • Confidence/Uncertainty pro Dimension berechnen                  │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐   │
│ │ Dimension 1: spec_similarity()      40%  + Evidence         │   │
│ │ Dimension 2: compliance_score()     25%  + Evidence         │   │
│ │ Dimension 3: price_delta_score()    15%  + Evidence         │   │
│ │ Dimension 4: lead_time_score()      10%  + Evidence         │   │
│ │ Dimension 5: quality_signals_score() 10% + Evidence         │   │
│ └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ Output: 5 Scores + 5 Evidence Trails + 5 Confidence Scores        │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ STUFE 2: COMPOSITE SCORE + UNCERTAINTY (composite.py)             │
│                                                                   │
│ composite = Σ (weight_i × score_i × confidence_i) / Σ weights     │
│                                                                   │
│ overall_confidence = Σ (weight_i × confidence_i) / Σ weights      │
│                                                                   │
│ Dann: Sortieren, Top 5, Explanations + Evidence generieren        │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ STUFE 3: BOM CONSOLIDATION (optional) (consolidation.py)          │
│                                                                   │
│ Wenn BOMContext vorhanden:                                        │
│ • Gruppiere ähnliche Materialien über Companies                   │
│ • Berechne Konsolidierungs-Potenzial                              │
│ • Empfehle gemeinsame Lieferanten                                 │
│                                                                   │
│ Output: ConsolidationResult                                       │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
OUTPUT: ScoringResult mit Evidence Trails + Uncertainty + Consolidation
```

## Evidence Trail System

Datei: evidence.py

### Zweck

Für jede Scoring-Entscheidung dokumentieren WOHER die Information kommt. Dies ist kritisch für die Challenge ("evidence trails and tradeoff explanations").

### Evidence-Typen

```python
class EvidenceType(Enum):
    SUPPLIER_DATABASE = "supplier_database"      # Aus Agnes/Spherecast DB
    SUPPLIER_WEBSITE = "supplier_website"        # Gecrawlt von Lieferanten-Website
    CERTIFICATION_DB = "certification_db"        # FDA, RoHS Datenbanken
    DATASHEET = "datasheet"                      # Technisches Datenblatt
    HISTORICAL_PROCUREMENT = "historical"        # Historische Einkaufsdaten
    EXTERNAL_API = "external_api"                # Externe API (z.B. Tariff-DB)
    CALCULATED = "calculated"                    # Berechnet/Abgeleitet
    USER_INPUT = "user_input"                    # Vom User angegeben
    INFERRED = "inferred"                        # Geschlussfolgert (niedriger Confidence)
```

### Evidence-Struktur

```python
@dataclass
class Evidence:
    type: EvidenceType
    source: str                     # z.B. "supplier_api.spherecast.com"
    field: str                      # z.B. "price", "zugfestigkeit"
    value: any                      # Der Wert
    timestamp: datetime             # Wann abgerufen
    confidence: float               # 0.0 bis 1.0
    url: str | None                 # Link zur Quelle wenn verfügbar
    notes: str | None               # Zusätzliche Infos

@dataclass 
class EvidenceTrail:
    dimension: str                  # z.B. "spec_similarity"
    evidences: list[Evidence]       # Alle Evidence-Einträge für diese Dimension
    overall_confidence: float       # Aggregierte Confidence
    data_completeness: float        # Wie viele Felder haben wir? 0.0-1.0
    data_freshness: str             # "current", "recent", "outdated"
```

### Evidence Collection

```python
def collect_evidence(
    field: str,
    value: any,
    source_type: EvidenceType,
    source_url: str = None,
    metadata: dict = None
) -> Evidence:
    """
    Erstellt einen Evidence-Eintrag für einen Datenpunkt.
    """
    
    # Confidence basierend auf Source-Type
    BASE_CONFIDENCE = {
        EvidenceType.CERTIFICATION_DB: 0.95,      # Offizielle Datenbank
        EvidenceType.DATASHEET: 0.90,             # Technisches Datenblatt
        EvidenceType.SUPPLIER_DATABASE: 0.85,     # Strukturierte DB
        EvidenceType.HISTORICAL_PROCUREMENT: 0.80, # Eigene Daten
        EvidenceType.SUPPLIER_WEBSITE: 0.70,      # Gecrawlt
        EvidenceType.EXTERNAL_API: 0.75,          # Externe API
        EvidenceType.USER_INPUT: 0.60,            # User-Angabe
        EvidenceType.CALCULATED: 0.70,            # Berechnet
        EvidenceType.INFERRED: 0.40,              # Geschlussfolgert
    }
    
    confidence = BASE_CONFIDENCE.get(source_type, 0.5)
    
    # Confidence-Adjustments
    if metadata:
        # Ältere Daten = niedrigere Confidence
        if "age_days" in metadata:
            age_factor = max(0.5, 1 - (metadata["age_days"] / 365))
            confidence *= age_factor
        
        # Mehr Datenpunkte = höhere Confidence
        if "sample_size" in metadata:
            if metadata["sample_size"] < 10:
                confidence *= 0.6
            elif metadata["sample_size"] < 100:
                confidence *= 0.8
    
    return Evidence(
        type=source_type,
        source=source_url or source_type.value,
        field=field,
        value=value,
        timestamp=datetime.now(),
        confidence=round(confidence, 3),
        url=source_url,
        notes=metadata.get("notes") if metadata else None
    )
```

## Uncertainty Handling

Datei: uncertainty.py

### Zweck

Explizit kommunizieren, wie sicher wir uns bei jeder Empfehlung sind. Challenge: "how the system handles uncertainty, evidence quality, and tradeoffs"

### Uncertainty-Levels

```python
class UncertaintyLevel(Enum):
    VERY_LOW = "very_low"       # > 90% Confidence
    LOW = "low"                 # 75-90% Confidence
    MEDIUM = "medium"           # 50-75% Confidence
    HIGH = "high"               # 25-50% Confidence
    VERY_HIGH = "very_high"     # < 25% Confidence
    INSUFFICIENT_DATA = "insufficient_data"  # Zu wenig Daten für Aussage

def confidence_to_uncertainty(confidence: float) -> UncertaintyLevel:
    if confidence >= 0.90:
        return UncertaintyLevel.VERY_LOW
    elif confidence >= 0.75:
        return UncertaintyLevel.LOW
    elif confidence >= 0.50:
        return UncertaintyLevel.MEDIUM
    elif confidence >= 0.25:
        return UncertaintyLevel.HIGH
    else:
        return UncertaintyLevel.VERY_HIGH
```

### Uncertainty-Report

```python
@dataclass
class UncertaintyReport:
    overall_level: UncertaintyLevel
    overall_confidence: float
    
    # Pro Dimension
    dimension_confidence: dict[str, float]
    dimension_uncertainty: dict[str, UncertaintyLevel]
    
    # Gründe für Unsicherheit
    uncertainty_reasons: list[str]
    
    # Empfehlungen
    data_gaps: list[str]                # Welche Daten fehlen
    verification_suggestions: list[str] # Was sollte verifiziert werden
    
    # Warnung wenn zu unsicher
    should_warn_user: bool
    warning_message: str | None

def generate_uncertainty_report(
    scored_candidate: ScoredCandidate,
    evidence_trails: dict[str, EvidenceTrail]
) -> UncertaintyReport:
    """
    Generiert einen Uncertainty-Report für einen Kandidaten.
    """
    
    dimension_confidence = {}
    uncertainty_reasons = []
    data_gaps = []
    verification_suggestions = []
    
    for dim, trail in evidence_trails.items():
        dimension_confidence[dim] = trail.overall_confidence
        
        # Gründe für niedrige Confidence sammeln
        if trail.overall_confidence < 0.5:
            if trail.data_completeness < 0.5:
                uncertainty_reasons.append(f"{dim}: Unvollständige Daten ({trail.data_completeness:.0%})")
                data_gaps.append(f"{dim}: Fehlende Datenpunkte")
            
            if trail.data_freshness == "outdated":
                uncertainty_reasons.append(f"{dim}: Veraltete Daten")
                verification_suggestions.append(f"{dim}: Aktuelle Daten vom Lieferanten anfordern")
            
            # Prüfe Evidence-Typen
            inferred_count = sum(1 for e in trail.evidences if e.type == EvidenceType.INFERRED)
            if inferred_count > len(trail.evidences) / 2:
                uncertainty_reasons.append(f"{dim}: Überwiegend abgeleitete Daten")
                verification_suggestions.append(f"{dim}: Direkte Bestätigung einholen")
    
    # Overall Confidence (gewichtet)
    weights = {"spec": 0.4, "compliance": 0.25, "price": 0.15, "lead_time": 0.1, "quality": 0.1}
    overall_confidence = sum(
        dimension_confidence.get(dim, 0) * w 
        for dim, w in weights.items()
    )
    
    overall_level = confidence_to_uncertainty(overall_confidence)
    
    # Warnung wenn zu unsicher
    should_warn = overall_confidence < 0.5
    warning_message = None
    if should_warn:
        warning_message = (
            f"Achtung: Diese Empfehlung basiert auf unvollständigen Daten "
            f"(Confidence: {overall_confidence:.0%}). "
            f"Vor einer Entscheidung sollten folgende Punkte verifiziert werden: "
            f"{', '.join(verification_suggestions[:3])}"
        )
    
    return UncertaintyReport(
        overall_level=overall_level,
        overall_confidence=overall_confidence,
        dimension_confidence=dimension_confidence,
        dimension_uncertainty={d: confidence_to_uncertainty(c) for d, c in dimension_confidence.items()},
        uncertainty_reasons=uncertainty_reasons,
        data_gaps=data_gaps,
        verification_suggestions=verification_suggestions,
        should_warn_user=should_warn,
        warning_message=warning_message
    )
```

### Uncertainty-aware Scoring

```python
def calculate_uncertainty_adjusted_score(
    raw_score: float,
    confidence: float,
    min_confidence_threshold: float = 0.3
) -> tuple[float, bool]:
    """
    Passt Score basierend auf Uncertainty an.
    
    Returns:
        (adjusted_score, is_reliable)
    """
    
    # Wenn Confidence unter Threshold, Score stark reduzieren
    if confidence < min_confidence_threshold:
        # Score wird auf 50% der Raw-Score reduziert + Warnung
        adjusted = raw_score * 0.5
        return (adjusted, False)
    
    # Confidence als Dämpfungsfaktor
    # Bei 100% Confidence: Score unverändert
    # Bei 50% Confidence: Score um 10% reduziert
    dampening = 1 - (1 - confidence) * 0.2
    adjusted = raw_score * dampening
    
    return (adjusted, True)
```

## Stufe 0: K.O.-Filter

Datei: knockout.py

### Zweck

Harte Ausschlusskriterien anwenden BEVOR das rechenintensive Scoring startet. Kandidaten die hier rausfliegen werden nicht gescored, sondern mit Begründung und Evidence in die rejected-Liste geschrieben.

### K.O.-Kriterien

| Kriterium | Prüfung | Beispiel |
|-----------|---------|----------|
| MOQ | moq > user_requirements.max_quantity | MOQ 1000 > Max 500 |
| Blacklist | country_of_origin in BLACKLIST[destination] | CN in US-Blacklist |
| Critical Certs | critical_certs - candidate_certs != empty | FDA fehlt |
| Max Lead Time | lead_time.days > user_requirements.max_lead_time | 90 > 60 Tage |
| Max Price | price > original_price * max_multiplier | 15€ > 10€ * 1.5 |

### Blacklist-Konfiguration

```python
COUNTRY_BLACKLIST = {
    "DE": ["KP", "IR", "SY"],           # Deutschland
    "US": ["KP", "IR", "CU", "RU"],     # USA
    "EU": ["KP", "IR", "SY"],           # EU allgemein
}
```

### Funktion mit Evidence

```python
def apply_knockout_filters(
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements
) -> KnockoutResult:
    """
    Filtert Kandidaten nach harten K.O.-Kriterien.
    Dokumentiert Evidence für jede Entscheidung.
    """
```

### Output mit Evidence

```python
@dataclass
class KnockoutResult:
    passed: list[CrawledMaterial]
    rejected: list[RejectedCandidate]
    
@dataclass
class RejectedCandidate:
    candidate: CrawledMaterial
    reasons: list[str]
    evidence: list[Evidence]            # NEU: Evidence für K.O.-Grund
    
    # Beispiel:
    # reasons: ["FDA fehlt"]
    # evidence: [
    #     Evidence(
    #         type=CERTIFICATION_DB,
    #         source="fda.gov/registration",
    #         field="fda_certification",
    #         value=None,
    #         notes="Keine FDA-Registrierung gefunden für Supplier X"
    #     )
    # ]
```

## Dimension 1: Spec Similarity (40%)

Datei: spec_similarity.py

### Zweck

Technische Eigenschaften (numerische Properties) zwischen Original und Kandidat vergleichen.

### Datentyp

Numerische Properties wie Zugfestigkeit, Dichte, Schmelzpunkt, E-Modul, etc.

### Methode

Cosine Similarity auf normalisierten Property-Vektoren.

### Algorithmus

```
Schritt 1: Gemeinsame Properties finden
           common_props = original.properties.keys() ∩ kandidat.properties.keys()

Schritt 2: Werte extrahieren
           vec_original = [original.properties[p].value for p in sorted(common_props)]
           vec_kandidat = [kandidat.properties[p].value for p in sorted(common_props)]

Schritt 3: Min-Max Normalisierung pro Property
           Nutze PROPERTY_RANGES für bekannte Properties
           normalized_value = (value - min) / (max - min)

Schritt 4: Cosine Similarity berechnen
           cos_sim = (A · B) / (||A|| × ||B||)

Schritt 5: Evidence sammeln
           Für jede Property: Quelle dokumentieren

Schritt 6: Confidence berechnen
           Basierend auf: Datenquellen, Vollständigkeit, Aktualität

Schritt 7: Score + Evidence + Confidence zurückgeben
```

### Property Ranges

```python
PROPERTY_RANGES = {
    "zugfestigkeit":      {"min": 1,     "max": 2000,   "unit": "MPa"},
    "dichte":             {"min": 0.1,   "max": 25.0,   "unit": "g/cm³"},
    "e_modul":            {"min": 100,   "max": 500000, "unit": "MPa"},
    "schmelzpunkt":       {"min": 50,    "max": 3500,   "unit": "°C"},
    "biegefestigkeit":    {"min": 1,     "max": 1000,   "unit": "MPa"},
    "haerte":             {"min": 1,     "max": 100,    "unit": "HRC"},
    "waermeleitfaehigkeit": {"min": 0.01, "max": 500,   "unit": "W/mK"},
    "bruchdehnung":       {"min": 0,     "max": 100,    "unit": "%"},
}
```

### Funktion

```python
def spec_similarity(
    original: CrawledMaterial,
    kandidat: CrawledMaterial
) -> SpecSimilarityResult:
    """
    Berechnet Spec Similarity zwischen zwei Materialien.
    Sammelt Evidence für alle verglichenen Properties.
    """
```

### Output mit Evidence

```python
@dataclass
class SpecSimilarityResult:
    score: float
    confidence: float                       # NEU
    evidence_trail: EvidenceTrail           # NEU
    
    common_props: list[str]
    missing_in_kandidat: list[str]
    extra_in_kandidat: list[str]
    details: dict[str, PropertyComparison]
    
@dataclass
class PropertyComparison:
    original_value: float
    kandidat_value: float
    original_normalized: float
    kandidat_normalized: float
    diff_percent: float
    
    # NEU: Evidence pro Property
    original_evidence: Evidence
    kandidat_evidence: Evidence
```

### Edge Cases

- Keine gemeinsamen Properties: score = 0.0, confidence = 0.0
- Property nicht in PROPERTY_RANGES: Dynamischer Range aus den zwei Werten
- Division by Zero bei Magnitude: score = 0.0
- Fehlende Datenquelle: confidence reduzieren, INFERRED Evidence-Type

## Dimension 2: Compliance Match (25%)

Datei: compliance.py

### Zweck

Prüfen, wie gut die Zertifizierungen des Kandidaten mit den Anforderungen übereinstimmen.

### Datentyp

Kategorische Listen (Sets von Zertifikaten).

### Methode

Set-Intersection mit Evidence-Tracking.

### Wichtig

Critical Certifications wurden bereits in Stufe 0 (K.O.-Filter) geprüft. Hier geht es um den GRAD der Übereinstimmung aller Zertifikate.

### Algorithmus mit Evidence

```
Schritt 1: Sets erstellen
           required = set(original.certifications)
           available = set(kandidat.certifications)

Schritt 2: Mengenoperationen
           matched = required ∩ available
           missing = required - available
           extra = available - required

Schritt 3: Für jedes Zertifikat: Evidence sammeln
           - Woher wissen wir dass Kandidat RoHS hat?
           - Certification DB? Supplier Website? Datasheet?

Schritt 4: Score berechnen
           score = len(matched) / len(required)

Schritt 5: Confidence berechnen
           - Verifizierte Zertifikate (aus offizieller DB) = hohe Confidence
           - Nur vom Supplier behauptet = niedrigere Confidence
```

### Funktion

```python
def compliance_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial
) -> ComplianceResult:
    """
    Berechnet Compliance Match mit Evidence Trail.
    """
```

### Output mit Evidence

```python
@dataclass
class ComplianceResult:
    score: float
    confidence: float                   # NEU
    evidence_trail: EvidenceTrail       # NEU
    
    matched: list[str]
    missing: list[str]
    extra: list[str]
    coverage: str
    
    # NEU: Evidence pro Zertifikat
    certification_evidence: dict[str, Evidence]
    # z.B. {"RoHS": Evidence(type=CERTIFICATION_DB, source="rohs-db.eu", ...)}
    
    # NEU: Welche Zertifikate sind nur behauptet vs. verifiziert
    verified_certs: list[str]
    claimed_only_certs: list[str]
```

### Bekannte Zertifikate mit Verification-Sources

```python
CERTIFICATION_VERIFICATION = {
    "RoHS": {
        "verification_sources": ["rohs-db.eu", "echa.europa.eu"],
        "self_declaration": True,
        "expiry_check": False
    },
    "FDA": {
        "verification_sources": ["fda.gov/registration"],
        "self_declaration": False,
        "expiry_check": True
    },
    "ISO9001": {
        "verification_sources": ["iso.org/certcheck"],
        "self_declaration": False,
        "expiry_check": True,
        "max_age_months": 36
    },
    # ... weitere
}
```

## Dimension 3: Price Delta (15%)

Datei: price_delta.py

### Zweck

Bewerten, wie sich der Preis des Kandidaten im Vergleich zum Original verhält.

### Datentyp

Einzelner Zahlenwert (Preis).

### Methode

Prozentuale Abweichung mit Capping und Evidence-Tracking.

### Preis-Adjustierungen mit Evidence

```
1. Incoterms berücksichtigen
   EXW: +15% (Evidence: CALCULATED, "Geschätzt basierend auf Standard-Shipping")
   FOB: +8%
   DDP: +0% (all-inclusive)

2. Tariffs addieren (Evidence: EXTERNAL_API, "tariff-api.trade.gov")
   CN → DE: +12%
   CN → US: +25%
   EU → DE: +0%

3. Price Tiers berücksichtigen (Evidence: SUPPLIER_DATABASE)
```

### Algorithmus

```
Schritt 1: Preise adjustieren + Evidence sammeln
           adjusted_original = adjust_price(original.price, ...)
           adjusted_kandidat = adjust_price(kandidat.price, ...)
           
           Evidence für jeden Adjustment-Schritt dokumentieren

Schritt 2: Delta berechnen
           delta_percent = ((adjusted_kandidat - adjusted_original) / adjusted_original) * 100

Schritt 3: Score berechnen
           Wenn delta_percent <= 0: score = 1.0
           Sonst: score = max(0.0, 1.0 - (delta_percent / max_penalty_percent))

Schritt 4: Confidence berechnen
           - Offizielle Preisliste = hohe Confidence
           - Geschätzte Shipping-Kosten = niedrigere Confidence
```

### Output mit Evidence

```python
@dataclass
class PriceDeltaResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail
    
    delta_percent: float
    delta_absolute: float
    direction: str
    original_price: float
    kandidat_price: float
    unit: str
    
    # NEU: Aufschlüsselung der Adjustments mit Evidence
    adjustments: list[PriceAdjustment]
    
@dataclass
class PriceAdjustment:
    type: str                   # "incoterm", "tariff", "tier"
    description: str
    amount: float
    evidence: Evidence
```

### Incoterm-Adjustments

```python
INCOTERM_ADJUSTMENTS = {
    "EXW": {"cost_adder": 0.15, "time_adder": 7, "description": "Ex Works"},
    "FOB": {"cost_adder": 0.08, "time_adder": 3, "description": "Free On Board"},
    "CIF": {"cost_adder": 0.05, "time_adder": 2, "description": "Cost Insurance Freight"},
    "DDP": {"cost_adder": 0.00, "time_adder": 0, "description": "Delivered Duty Paid"},
}
```

### Tariff-Tabelle

```python
TARIFF_RATES = {
    ("CN", "DE"): 0.12,
    ("CN", "US"): 0.25,
    ("VN", "DE"): 0.05,
    ("IN", "DE"): 0.08,
    ("DE", "DE"): 0.00,
    ("EU", "DE"): 0.00,
    ("US", "DE"): 0.05,
}
```

## Dimension 4: Lead Time (10%)

Datei: lead_time.py

### Zweck

Bewerten, wie schnell der Kandidat verfügbar ist im Vergleich zum Original.

### Datentyp

Zeitwert (Tage).

### Methode

Verhältnis-Score mit Toleranzbereich, Reliability-Adjustment und Evidence-Tracking.

### Algorithmus

```
Schritt 1: Lead Times extrahieren + Evidence
           days_original = original.lead_time.days
           days_kandidat = kandidat.lead_time.days
           
           Evidence: Woher kommt die Lead Time Info?
           - Supplier API = hohe Confidence
           - Historische Bestellungen = hohe Confidence
           - Supplier Website = mittlere Confidence
           - Geschätzt = niedrige Confidence

Schritt 2: Incoterm-Adjustment
           days_kandidat += INCOTERM_ADJUSTMENTS[kandidat.incoterm]["time_adder"]

Schritt 3: Stock-Check
           Wenn kandidat.stock > 0: days_kandidat = 0 bis 3

Schritt 4: Score berechnen (wie zuvor)

Schritt 5: Confidence berechnen
           Basierend auf: Datenquelle, Reliability-Historie, Aktualität
```

### Output mit Evidence

```python
@dataclass
class LeadTimeResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail
    
    base_score: float
    days_original: int
    days_kandidat: int
    days_difference: int
    direction: str
    percent_change: float
    reliability_original: float
    reliability_kandidat: float
    risk_level: str
    tolerance_applied: bool
    
    # NEU: Evidence für Lead Time Quellen
    lead_time_evidence: Evidence
    reliability_evidence: Evidence | None
    stock_evidence: Evidence | None
```

### Risk Level Bestimmung

```python
def determine_risk_level(days_difference, percent_change, reliability, confidence) -> str:
    # Niedrige Confidence erhöht Risk Level
    if confidence < 0.5:
        return "high"  # Immer mindestens "high" bei niedriger Confidence
    
    if days_difference <= 0:
        return "low"
    if days_difference <= 3 and reliability >= 0.9:
        return "low"
    if days_difference <= 7 and reliability >= 0.8:
        return "medium"
    if percent_change > 100 or reliability < 0.7:
        return "critical"
    return "high"
```

## Dimension 5: Quality Signals (10%)

Datei: quality_signals.py

### Zweck

Bewerten, wie vertrauenswürdig ein Kandidat und sein Lieferant sind.

### Datentyp

Multiple Signale mit unterschiedlicher Verfügbarkeit und Verlässlichkeit.

### Methode

Gewichteter Durchschnitt mit Confidence-Adjustment, dynamischer Gewichtsverteilung und umfangreichem Evidence-Tracking.

### Signale und Gewichte

| Signal | Gewicht | Normalisierung | Confidence-Faktoren |
|--------|---------|----------------|---------------------|
| supplier_rating | 25% | value / 5.0 | review_count (min 100), platform |
| defect_rate | 25% | 1 - (value / 5.0) | sample_size (min 1000), period |
| on_time_delivery | 20% | value / 100 | sample_size (min 50) |
| audit_score | 15% | value / 100 | auditor, age (max 24 months) |
| years_in_business | 10% | min(value / 10, 1.0) | immer 1.0 |
| sample_test | 5% | 1.0 wenn passed, sonst 0.0 | immer 1.0 |

### Output mit Evidence

```python
@dataclass
class QualitySignalsResult:
    score: float
    confidence: float                       # Overall Confidence
    evidence_trail: EvidenceTrail
    
    signals: dict[str, SignalResult]
    overall_confidence: float
    missing_signals: list[str]
    risk_factors: list[str]

@dataclass
class SignalResult:
    score: float | None
    weight_used: float
    confidence: float
    notes: str
    evidence: Evidence                      # NEU: Evidence pro Signal
```

## Composite Score

Datei: composite.py

### Zweck

Alle 5 Dimension-Scores zu einem Gesamtscore zusammenführen, unter Berücksichtigung von Confidence.

### Formel (Confidence-weighted)

```python
def calculate_composite_score(
    dimension_scores: dict[str, float],
    dimension_confidences: dict[str, float],
    weights: dict[str, float] = None
) -> CompositeResult:
    """
    Berechnet Confidence-gewichteten Composite Score.
    
    Formel:
    composite = Σ (weight_i × score_i × confidence_i) / Σ (weight_i × confidence_i)
    
    Bei niedriger Confidence wird der Score gedämpft.
    """
    
    if weights is None:
        weights = {
            "spec": 0.40, "compliance": 0.25, "price": 0.15,
            "lead_time": 0.10, "quality": 0.10
        }
    
    weighted_sum = 0
    weight_sum = 0
    
    for dim, weight in weights.items():
        score = dimension_scores.get(dim, 0)
        confidence = dimension_confidences.get(dim, 0.5)
        
        # Confidence wirkt als Dämpfung
        effective_weight = weight * confidence
        weighted_sum += score * effective_weight
        weight_sum += effective_weight
    
    if weight_sum == 0:
        return CompositeResult(score=0, confidence=0, ...)
    
    composite_score = weighted_sum / weight_sum
    overall_confidence = sum(
        weights[d] * dimension_confidences.get(d, 0.5) 
        for d in weights
    ) / sum(weights.values())
    
    return CompositeResult(
        score=composite_score,
        confidence=overall_confidence,
        ...
    )
```

### Konfigurierbare Gewichte

```python
WEIGHT_PRESETS = {
    "default": {
        "spec": 0.40, "compliance": 0.25, "price": 0.15,
        "lead_time": 0.10, "quality": 0.10
    },
    "cost_focused": {
        "spec": 0.30, "compliance": 0.20, "price": 0.35,
        "lead_time": 0.05, "quality": 0.10
    },
    "availability_focused": {
        "spec": 0.30, "compliance": 0.20, "price": 0.10,
        "lead_time": 0.30, "quality": 0.10
    },
    "quality_focused": {
        "spec": 0.35, "compliance": 0.25, "price": 0.10,
        "lead_time": 0.05, "quality": 0.25
    },
}
```

## BOM Consolidation Layer

Datei: consolidation.py

### Zweck

Challenge-Anforderung: "supplier consolidation" — Wenn mehrere Companies ähnliche Materialien kaufen, gemeinsamen Lieferanten empfehlen.

### Konzept

```
Company A kauft: Aluminium 6061 von Supplier X (500 kg/Monat)
Company B kauft: Aluminium 6061 von Supplier Y (300 kg/Monat)
Company C kauft: Aluminium 6063 von Supplier Z (200 kg/Monat)

→ Konsolidierungs-Empfehlung:
  "Alle drei könnten von Supplier X kaufen:
   - Gesamtvolumen: 1000 kg/Monat
   - Bessere Preis-Tier: -12%
   - Ein Lieferant statt drei"
```

### Input

```python
@dataclass
class BOMContext:
    company_boms: dict[str, list[BOMEntry]]  # Company → ihre BOM-Einträge
    historical_procurement: list[ProcurementRecord]
    consolidation_goals: ConsolidationGoals

@dataclass
class BOMEntry:
    material_id: str
    material_name: str
    quantity_per_month: float
    current_supplier: str
    current_price: float

@dataclass
class ConsolidationGoals:
    max_suppliers_per_category: int = 2
    min_savings_percent: float = 5.0
    allow_spec_deviation_percent: float = 10.0
```

### Algorithmus

```python
def calculate_consolidation(
    bom_context: BOMContext,
    scored_candidates: list[ScoredCandidate]
) -> ConsolidationResult:
    """
    Berechnet Konsolidierungs-Potenzial über mehrere Companies.
    """
    
    # 1. Gruppiere ähnliche Materialien
    material_groups = group_similar_materials(
        bom_context.company_boms,
        similarity_threshold=0.85
    )
    
    # 2. Für jede Gruppe: Finde gemeinsamen Supplier
    consolidation_opportunities = []
    
    for group in material_groups:
        # Kombiniertes Volumen
        total_volume = sum(entry.quantity_per_month for entry in group.entries)
        
        # Finde Kandidaten die alle beliefern könnten
        common_candidates = find_common_candidates(group, scored_candidates)
        
        for candidate in common_candidates:
            # Berechne Savings durch bessere Price Tier
            new_price = get_tier_price(candidate, total_volume)
            current_total_cost = sum(e.quantity_per_month * e.current_price for e in group.entries)
            new_total_cost = total_volume * new_price
            
            savings_percent = (current_total_cost - new_total_cost) / current_total_cost * 100
            
            if savings_percent >= bom_context.consolidation_goals.min_savings_percent:
                consolidation_opportunities.append(
                    ConsolidationOpportunity(
                        material_group=group,
                        recommended_supplier=candidate,
                        combined_volume=total_volume,
                        savings_percent=savings_percent,
                        current_supplier_count=len(set(e.current_supplier for e in group.entries)),
                        new_supplier_count=1
                    )
                )
    
    return ConsolidationResult(
        opportunities=consolidation_opportunities,
        total_potential_savings=sum(o.savings_percent for o in consolidation_opportunities),
        supplier_reduction=calculate_supplier_reduction(consolidation_opportunities)
    )
```

### Output

```python
@dataclass
class ConsolidationResult:
    opportunities: list[ConsolidationOpportunity]
    total_potential_savings: float
    supplier_reduction: int                     # Anzahl Lieferanten die wegfallen
    evidence_trail: EvidenceTrail

@dataclass
class ConsolidationOpportunity:
    material_group: MaterialGroup
    recommended_supplier: ScoredCandidate
    combined_volume: float
    savings_percent: float
    savings_absolute: float
    current_supplier_count: int
    new_supplier_count: int
    companies_affected: list[str]
    
    # Tradeoffs dokumentieren
    tradeoffs: list[str]
    # z.B. ["Company B muss auf leicht anderen Spec wechseln (97% Similarity)"]
```

## Explanation Generator

Datei: explanation.py

### Zweck

Menschenlesbare Erklärungen mit Evidence Trails generieren.

### Struktur mit Evidence

```python
@dataclass
class Explanation:
    summary: str
    recommendation: str
    confidence_statement: str           # NEU: "Hohe Sicherheit" / "Mit Vorbehalt"
    
    strengths: list[StrengthItem]
    weaknesses: list[WeaknessItem]
    risks: list[str]
    
    score_breakdown: dict[str, str]
    evidence_summary: list[str]         # NEU: "Preis basierend auf Supplier-Datenbank"
    
    uncertainty_warning: str | None     # NEU: Warnung wenn unsicher
    verification_needed: list[str]      # NEU: Was sollte verifiziert werden

@dataclass
class StrengthItem:
    text: str
    evidence: str                       # NEU: "Basierend auf TÜV-Audit vom März 2024"
    confidence: float

@dataclass
class WeaknessItem:
    text: str
    evidence: str
    confidence: float
    mitigation: str | None              # NEU: Wie könnte man das mitigieren?
```

### Logik

```python
def generate_explanation(
    scored_candidate: ScoredCandidate,
    evidence_trails: dict[str, EvidenceTrail],
    uncertainty_report: UncertaintyReport
) -> Explanation:
    """
    Generiert Explanation mit Evidence und Uncertainty.
    """
    
    scores = scored_candidate.scores
    composite = scored_candidate.composite_score
    overall_confidence = uncertainty_report.overall_confidence
    
    # Confidence Statement
    if overall_confidence >= 0.8:
        confidence_statement = "Hohe Sicherheit: Diese Empfehlung basiert auf verifizierten Daten."
    elif overall_confidence >= 0.6:
        confidence_statement = "Gute Datenbasis: Die meisten Daten sind verifiziert."
    elif overall_confidence >= 0.4:
        confidence_statement = "Mit Vorbehalt: Einige Daten sollten vor Entscheidung verifiziert werden."
    else:
        confidence_statement = "Niedrige Sicherheit: Empfehlung basiert auf unvollständigen Daten."
    
    # Strengths mit Evidence
    strengths = []
    for dim, score in scores.items():
        if score >= 0.8:
            trail = evidence_trails.get(dim)
            evidence_text = summarize_evidence(trail) if trail else "Keine Quellenangabe"
            
            strengths.append(StrengthItem(
                text=STRENGTH_MESSAGES[dim],
                evidence=evidence_text,
                confidence=trail.overall_confidence if trail else 0.5
            ))
    
    # Weaknesses mit Evidence und Mitigation
    weaknesses = []
    for dim, score in scores.items():
        if score < 0.5:
            trail = evidence_trails.get(dim)
            detail = scored_candidate.details.get(dim)
            
            weaknesses.append(WeaknessItem(
                text=format_weakness(dim, detail),
                evidence=summarize_evidence(trail) if trail else "Keine Quellenangabe",
                confidence=trail.overall_confidence if trail else 0.5,
                mitigation=suggest_mitigation(dim, detail)
            ))
    
    # Evidence Summary
    evidence_summary = []
    for dim, trail in evidence_trails.items():
        for evidence in trail.evidences[:2]:  # Top 2 pro Dimension
            evidence_summary.append(
                f"{dim}: {evidence.field} aus {evidence.source}"
            )
    
    # Summary mit Confidence
    if composite >= 0.85 and overall_confidence >= 0.7:
        summary = "Exzellente Alternative (hohe Sicherheit)"
        recommendation = "Empfohlen"
    elif composite >= 0.70 and overall_confidence >= 0.5:
        summary = "Gute Alternative"
        recommendation = "Empfohlen"
    elif composite >= 0.55:
        summary = "Akzeptable Alternative"
        recommendation = "Bedingt empfohlen"
    else:
        summary = "Schwache Alternative"
        recommendation = "Nicht empfohlen"
    
    # Bei niedriger Confidence: Recommendation downgraden
    if overall_confidence < 0.4 and recommendation == "Empfohlen":
        recommendation = "Bedingt empfohlen (Daten verifizieren)"
    
    return Explanation(
        summary=summary,
        recommendation=recommendation,
        confidence_statement=confidence_statement,
        strengths=strengths,
        weaknesses=weaknesses,
        risks=uncertainty_report.uncertainty_reasons,
        score_breakdown={dim: f"{score*100:.0f}%" for dim, score in scores.items()},
        evidence_summary=evidence_summary,
        uncertainty_warning=uncertainty_report.warning_message,
        verification_needed=uncertainty_report.verification_suggestions
    )

def suggest_mitigation(dimension: str, detail: any) -> str | None:
    """
    Schlägt Mitigation für Schwächen vor.
    """
    mitigations = {
        "price": "Mengenrabatt verhandeln oder alternative Incoterms prüfen",
        "lead_time": "Express-Shipping anfragen oder Lagerbestand beim Supplier prüfen",
        "compliance": "Fehlende Zertifikate beim Supplier anfragen",
        "quality": "Sample-Bestellung zur Qualitätsprüfung anfordern",
        "spec": "Technische Freigabe durch Engineering einholen"
    }
    return mitigations.get(dimension)
```

## Pipeline

Datei: pipeline.py

### Hauptfunktion

```python
def find_substitutes(
    original: CrawledMaterial,
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements,
    weights: dict[str, float] = None,
    top_n: int = 5,
    bom_context: BOMContext = None
) -> ScoringResult:
    """
    Vollständige Substitution-Scoring-Pipeline mit Evidence und Uncertainty.
    """
    
    # Stufe 0: K.O.-Filter
    knockout_result = apply_knockout_filters(candidates, user_requirements)
    
    # Stufe 1 + 2: Scoring mit Evidence Collection
    scored_candidates = []
    
    for kandidat in knockout_result.passed:
        # Alle Dimensionen berechnen
        spec_result = spec_similarity(original, kandidat)
        compliance_result = compliance_score(original, kandidat)
        price_result = price_delta_score(original, kandidat, user_requirements)
        lead_time_result = lead_time_score(original, kandidat)
        quality_result = quality_signals_score(original, kandidat)
        
        # Scores und Confidences sammeln
        scores = {
            "spec": spec_result.score,
            "compliance": compliance_result.score,
            "price": price_result.score,
            "lead_time": lead_time_result.score,
            "quality": quality_result.score
        }
        
        confidences = {
            "spec": spec_result.confidence,
            "compliance": compliance_result.confidence,
            "price": price_result.confidence,
            "lead_time": lead_time_result.confidence,
            "quality": quality_result.confidence
        }
        
        evidence_trails = {
            "spec": spec_result.evidence_trail,
            "compliance": compliance_result.evidence_trail,
            "price": price_result.evidence_trail,
            "lead_time": lead_time_result.evidence_trail,
            "quality": quality_result.evidence_trail
        }
        
        # Composite Score (Confidence-weighted)
        composite = calculate_composite_score(scores, confidences, weights)
        
        # Uncertainty Report
        uncertainty = generate_uncertainty_report(
            ScoredCandidate(kandidat, scores, composite.score),
            evidence_trails
        )
        
        scored_candidates.append(ScoredCandidate(
            kandidat=kandidat,
            scores=scores,
            confidences=confidences,
            composite_score=composite.score,
            overall_confidence=composite.confidence,
            evidence_trails=evidence_trails,
            uncertainty_report=uncertainty
        ))
    
    # Sortieren nach Composite Score
    scored_candidates.sort(key=lambda x: x.composite_score, reverse=True)
    top_candidates = scored_candidates[:top_n]
    
    # Explanations generieren
    for rank, candidate in enumerate(top_candidates, 1):
        candidate.rank = rank
        candidate.explanation = generate_explanation(
            candidate,
            candidate.evidence_trails,
            candidate.uncertainty_report
        )
    
    # Stufe 3: BOM Consolidation (optional)
    consolidation = None
    if bom_context:
        consolidation = calculate_consolidation(bom_context, scored_candidates)
    
    return ScoringResult(
        original=original,
        top_candidates=top_candidates,
        rejected=knockout_result.rejected,
        metadata=ScoringMetadata(
            weights=weights or WEIGHT_PRESETS["default"],
            total_candidates=len(candidates),
            passed_knockout=len(knockout_result.passed),
            average_confidence=sum(c.overall_confidence for c in top_candidates) / len(top_candidates) if top_candidates else 0
        ),
        consolidation=consolidation
    )
```

## Testing

### Teststruktur

```
tests/scoring/
├── conftest.py
├── test_knockout.py
├── test_spec_similarity.py
├── test_compliance.py
├── test_price_delta.py
├── test_lead_time.py
├── test_quality_signals.py
├── test_composite.py
├── test_evidence.py            # NEU
├── test_uncertainty.py         # NEU
├── test_consolidation.py       # NEU
├── test_explanation.py         # NEU
├── test_pipeline.py
└── test_edge_cases.py
```

### Wichtige Test-Szenarien

Evidence Trail:
- Alle Daten haben Evidence
- Fehlende Evidence → niedrige Confidence
- Verschiedene Evidence-Typen (DB vs. Inferred)
- Evidence-Alter beeinflusst Confidence

Uncertainty:
- Hohe Confidence → keine Warnung
- Niedrige Confidence → Warnung + Verification Suggestions
- Insufficient Data Handling
- Uncertainty-adjusted Scoring

Consolidation:
- Keine BOM → kein Consolidation Result
- Ähnliche Materialien werden gruppiert
- Savings korrekt berechnet
- Tradeoffs dokumentiert

## Beispiel-Aufruf

```python
from shared.schemas import CrawledMaterial, UserRequirements, BOMContext
from src.scoring.pipeline import find_substitutes

# Scoring mit Evidence und Uncertainty
result = find_substitutes(
    original=original_material,
    candidates=crawled_candidates,
    user_requirements=requirements,
    weights=None,
    top_n=5,
    bom_context=bom_context  # Optional
)

# Ergebnis mit Evidence
top = result.top_candidates[0]
print(f"Top Kandidat: {top.kandidat.name}")
print(f"Score: {top.composite_score:.0%}")
print(f"Confidence: {top.overall_confidence:.0%}")
print(f"Empfehlung: {top.explanation.recommendation}")

# Evidence Trail
for dim, trail in top.evidence_trails.items():
    print(f"\n{dim} Evidence:")
    for ev in trail.evidences:
        print(f"  - {ev.field}: {ev.value} (Source: {ev.source}, Confidence: {ev.confidence:.0%})")

# Uncertainty Warning
if top.explanation.uncertainty_warning:
    print(f"\n⚠️ {top.explanation.uncertainty_warning}")

# Verification Needed
if top.explanation.verification_needed:
    print("\nZu verifizieren:")
    for item in top.explanation.verification_needed:
        print(f"  - {item}")

# Consolidation (wenn BOM vorhanden)
if result.consolidation:
    print(f"\nKonsolidierungs-Potenzial: {result.consolidation.total_potential_savings:.1f}%")
    for opp in result.consolidation.opportunities:
        print(f"  - {opp.recommended_supplier.kandidat.name}: {opp.savings_percent:.1f}% Ersparnis")
```

## Wichtige Design-Entscheidungen

| Entscheidung | Begründung |
|--------------|------------|
| K.O. vor Scoring | Performance, keine unnötigen Berechnungen |
| Scores zwischen 0 und 1 | Einheitlich, einfach zu gewichten |
| Evidence Trail pro Dimension | Challenge: "evidence trails and tradeoff explanations" |
| Confidence-weighted Scoring | Challenge: "uncertainty, evidence quality" |
| Uncertainty Warnings | Transparenz, verhindert falsche Sicherheit |
| BOM Consolidation optional | Nicht jede Anfrage hat BOM-Kontext |
| Verification Suggestions | Actionable Insights für User |

## Dependencies

```
numpy           # Vektor-Operationen, Cosine Similarity
dataclasses     # Datenstrukturen
typing          # Type Hints
math            # sqrt, etc.
datetime        # Evidence Timestamps
enum            # EvidenceType, UncertaintyLevel
```