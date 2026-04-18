# CLAUDE.md — Scoring Modul

## Überblick

Dieses Modul ist verantwortlich für das 5-dimensionale Scoring-System zur Bewertung von Material-Substituten. Es nimmt normalisierte Materialdaten vom Crawling-Modul entgegen und liefert ein Ranking mit Explanations an das UI-Modul.

## Input und Output

### Input (vom Crawling-Modul)

```python
original: CrawledMaterial           # Das zu ersetzende Material
candidates: list[CrawledMaterial]   # Alle potenziellen Ersatzmaterialien
user_requirements: UserRequirements # K.O.-Kriterien und Präferenzen
```

### Output (für UI-Modul)

```python
ScoringResult(
    original: CrawledMaterial,
    top_candidates: list[ScoredCandidate],  # Top 5 mit Scores und Explanations
    rejected: list[RejectedCandidate],       # K.O.-gefilterte mit Gründen
    metadata: ScoringMetadata                # Weights, counts, config
)
```

## Dateistruktur

```
src/scoring/
├── CLAUDE.md              # Diese Datei
├── __init__.py            # Exports
├── knockout.py            # Stufe 0: K.O.-Filter
├── spec_similarity.py     # Dimension 1: Spec Similarity (40%)
├── compliance.py          # Dimension 2: Compliance Match (25%)
├── price_delta.py         # Dimension 3: Price Delta (15%)
├── lead_time.py           # Dimension 4: Lead Time (10%)
├── quality_signals.py     # Dimension 5: Quality Signals (10%)
├── composite.py           # Composite Score Berechnung
└── pipeline.py            # Orchestrierung der gesamten Pipeline
```

## Pipeline-Architektur

```
INPUT: list[CrawledMaterial]
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
│ Output: max. 15 Kandidaten                                        │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ STUFE 1: 5D SCORING                                               │
│                                                                   │
│ Für jeden Kandidaten alle 5 Dimensionen berechnen:                │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐   │
│ │ Dimension 1: spec_similarity()      40%                     │   │
│ │ Dimension 2: compliance_score()     25%                     │   │
│ │ Dimension 3: price_delta_score()    15%                     │   │
│ │ Dimension 4: lead_time_score()      10%                     │   │
│ │ Dimension 5: quality_signals_score() 10%                    │   │
│ └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ Output: 5 Scores pro Kandidat, jeweils zwischen 0 und 1           │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│ STUFE 2: COMPOSITE SCORE (composite.py)                           │
│                                                                   │
│ composite = 0.40 × spec                                           │
│           + 0.25 × compliance                                     │
│           + 0.15 × price                                          │
│           + 0.10 × lead_time                                      │
│           + 0.10 × quality                                        │
│                                                                   │
│ Dann: Sortieren, Top 5, Explanations generieren                   │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
OUTPUT: ScoringResult
```

## Stufe 0: K.O.-Filter

Datei: knockout.py

### Zweck

Harte Ausschlusskriterien anwenden BEVOR das rechenintensive Scoring startet. Kandidaten die hier rausfliegen werden nicht gescored, sondern mit Begründung in die rejected-Liste geschrieben.

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

### Funktion

```python
def apply_knockout_filters(
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements
) -> KnockoutResult:
    """
    Filtert Kandidaten nach harten K.O.-Kriterien.
    
    Args:
        candidates: Alle Kandidaten vom Crawling
        user_requirements: User-definierte Anforderungen
        
    Returns:
        KnockoutResult mit passed (max 15) und rejected (mit Gründen)
    """
```

### Output

```python
@dataclass
class KnockoutResult:
    passed: list[CrawledMaterial]           # Max 15 Kandidaten
    rejected: list[RejectedCandidate]       # Mit Ablehnungsgründen
    
@dataclass
class RejectedCandidate:
    candidate: CrawledMaterial
    reasons: list[str]                      # z.B. ["MOQ (1000) > Max (500)", "FDA fehlt"]
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

Schritt 5: Score zurückgeben
           score = cos_sim  (bereits zwischen 0 und 1)
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
    
    Returns:
        SpecSimilarityResult mit score, common_props, details
    """
```

### Output

```python
@dataclass
class SpecSimilarityResult:
    score: float                            # 0.0 bis 1.0
    common_props: list[str]                 # Verglichene Properties
    missing_in_kandidat: list[str]          # Properties nur im Original
    extra_in_kandidat: list[str]            # Properties nur im Kandidat
    details: dict[str, PropertyComparison]  # Pro-Property Breakdown
    
@dataclass
class PropertyComparison:
    original_value: float
    kandidat_value: float
    original_normalized: float
    kandidat_normalized: float
    diff_percent: float
```

### Edge Cases

- Keine gemeinsamen Properties: score = 0.0
- Property nicht in PROPERTY_RANGES: Dynamischer Range aus den zwei Werten
- Division by Zero bei Magnitude: score = 0.0

## Dimension 2: Compliance Match (25%)

Datei: compliance.py

### Zweck

Prüfen, wie gut die Zertifizierungen des Kandidaten mit den Anforderungen übereinstimmen.

### Datentyp

Kategorische Listen (Sets von Zertifikaten).

### Methode

Set-Intersection.

### Wichtig

Critical Certifications wurden bereits in Stufe 0 (K.O.-Filter) geprüft. Hier geht es um den GRAD der Übereinstimmung aller Zertifikate.

### Algorithmus

```
Schritt 1: Sets erstellen
           required = set(original.certifications)
           available = set(kandidat.certifications)

Schritt 2: Mengenoperationen
           matched = required ∩ available
           missing = required - available
           extra = available - required

Schritt 3: Score berechnen
           score = len(matched) / len(required)
           
           Wenn required leer: score = 1.0
```

### Funktion

```python
def compliance_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial
) -> ComplianceResult:
    """
    Berechnet Compliance Match zwischen zwei Materialien.
    
    Returns:
        ComplianceResult mit score, matched, missing, extra
    """
```

### Output

```python
@dataclass
class ComplianceResult:
    score: float                # 0.0 bis 1.0
    matched: list[str]          # z.B. ["RoHS", "REACH"]
    missing: list[str]          # z.B. ["FDA", "UL94"]
    extra: list[str]            # z.B. ["ISO14001"]
    coverage: str               # z.B. "3/5"
```

### Bekannte Zertifikate

```python
KNOWN_CERTIFICATIONS = {
    # Umwelt/Chemie
    "RoHS", "REACH", "WEEE", "PFAS-free",
    
    # Lebensmittel/Medizin
    "FDA", "EU-10/2011", "NSF", "USP-Class-VI",
    
    # Brandschutz
    "UL94-V0", "UL94-V1", "UL94-V2", "UL94-HB",
    
    # Qualitätsmanagement
    "ISO9001", "ISO14001", "IATF16949", "AS9100",
    
    # Automobil
    "PPAP", "IMDS",
    
    # Elektro
    "CE", "UL", "CSA", "TÜV",
}
```

## Dimension 3: Price Delta (15%)

Datei: price_delta.py

### Zweck

Bewerten, wie sich der Preis des Kandidaten im Vergleich zum Original verhält.

### Datentyp

Einzelner Zahlenwert (Preis).

### Methode

Prozentuale Abweichung mit Capping.

### Preis-Adjustierungen

Vor dem Vergleich müssen die Preise für faire Vergleichbarkeit adjustiert werden:

```
1. Incoterms berücksichtigen
   EXW: +15% (geschätzte Shipping/Customs)
   FOB: +8%
   DDP: +0% (all-inclusive)

2. Tariffs addieren (basierend auf Country of Origin)
   CN → DE: +12%
   CN → US: +25%
   EU → DE: +0%

3. Price Tiers berücksichtigen (effektiver Preis bei User's Quantity)
```

### Algorithmus

```
Schritt 1: Preise adjustieren
           adjusted_original = adjust_price(original.price, original.incoterm, ...)
           adjusted_kandidat = adjust_price(kandidat.price, kandidat.incoterm, ...)

Schritt 2: Delta berechnen
           delta_percent = ((adjusted_kandidat - adjusted_original) / adjusted_original) * 100

Schritt 3: Score berechnen
           Wenn delta_percent <= 0 (günstiger oder gleich):
               score = 1.0
           Sonst:
               score = max(0.0, 1.0 - (delta_percent / max_penalty_percent))
           
           Default max_penalty_percent = 50 (bei +50% ist score = 0)
```

### Funktion

```python
def price_delta_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
    user_quantity: int = None,
    destination_country: str = "DE",
    max_penalty_percent: float = 50.0
) -> PriceDeltaResult:
    """
    Berechnet Price Delta Score zwischen zwei Materialien.
    
    Returns:
        PriceDeltaResult mit score, delta_percent, adjustments
    """
```

### Output

```python
@dataclass
class PriceDeltaResult:
    score: float                    # 0.0 bis 1.0
    delta_percent: float            # z.B. 20.0 (20% teurer)
    delta_absolute: float           # z.B. 2.50 (€/kg)
    direction: str                  # "teurer", "günstiger", "gleich"
    original_price: float           # Adjustierter Originalpreis
    kandidat_price: float           # Adjustierter Kandidatpreis
    unit: str                       # z.B. "€/kg"
    adjustments: PriceAdjustments   # Details zu Incoterm/Tariff Adjustments
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
    ("CN", "DE"): 0.12,     # China nach Deutschland
    ("CN", "US"): 0.25,     # China nach USA
    ("VN", "DE"): 0.05,     # Vietnam nach Deutschland
    ("IN", "DE"): 0.08,     # Indien nach Deutschland
    ("DE", "DE"): 0.00,     # Inland
    ("EU", "DE"): 0.00,     # EU-intern
    ("US", "DE"): 0.05,     # USA nach Deutschland
}
```

## Dimension 4: Lead Time (10%)

Datei: lead_time.py

### Zweck

Bewerten, wie schnell der Kandidat verfügbar ist im Vergleich zum Original.

### Datentyp

Zeitwert (Tage).

### Methode

Verhältnis-Score mit Toleranzbereich und optionalem Reliability-Adjustment.

### Algorithmus

```
Schritt 1: Lead Times extrahieren
           days_original = original.lead_time.days
           days_kandidat = kandidat.lead_time.days
           
           Incoterm-Adjustment addieren:
           days_kandidat += INCOTERM_ADJUSTMENTS[kandidat.incoterm]["time_adder"]

Schritt 2: Stock-Check
           Wenn kandidat.stock > 0: days_kandidat = 0 bis 3

Schritt 3: Toleranz prüfen
           Wenn abs(days_kandidat - days_original) <= tolerance_days:
               base_score = 1.0

Schritt 4: Score berechnen
           Wenn days_kandidat <= days_original:
               base_score = 1.0 (schneller oder gleich, kein Bonus über 1.0)
           Sonst:
               base_score = days_original / days_kandidat

Schritt 5: Reliability-Adjustment (optional)
           reliability_ratio = kandidat.reliability / original.reliability
           adjustment = 1 + 0.2 * (reliability_ratio - 1)
           final_score = base_score * adjustment
           final_score = clamp(final_score, 0.0, 1.0)
```

### Funktion

```python
def lead_time_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
    tolerance_days: int = 3,
    use_reliability: bool = True
) -> LeadTimeResult:
    """
    Berechnet Lead Time Score zwischen zwei Materialien.
    
    Returns:
        LeadTimeResult mit score, days_difference, risk_level
    """
```

### Output

```python
@dataclass
class LeadTimeResult:
    score: float                    # 0.0 bis 1.0
    base_score: float               # Score vor Reliability-Adjustment
    days_original: int
    days_kandidat: int
    days_difference: int            # Positiv = länger, negativ = kürzer
    direction: str                  # "länger", "kürzer", "gleich"
    percent_change: float
    reliability_original: float
    reliability_kandidat: float
    risk_level: str                 # "low", "medium", "high", "critical"
    tolerance_applied: bool         # True wenn innerhalb Toleranz
```

### Risk Level Bestimmung

```python
def determine_risk_level(days_difference, percent_change, reliability) -> str:
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

Bewerten, wie vertrauenswürdig ein Kandidat und sein Lieferant sind, basierend auf verschiedenen Qualitätsindikatoren.

### Datentyp

Multiple Signale mit unterschiedlicher Verfügbarkeit und Verlässlichkeit.

### Methode

Gewichteter Durchschnitt mit Confidence-Adjustment und dynamischer Gewichtsverteilung bei fehlenden Signalen.

### Signale und Gewichte

| Signal | Gewicht | Normalisierung | Confidence-Faktoren |
|--------|---------|----------------|---------------------|
| supplier_rating | 25% | value / 5.0 | review_count (min 100) |
| defect_rate | 25% | 1 - (value / 5.0) | sample_size (min 1000), period |
| on_time_delivery | 20% | value / 100 | sample_size (min 50) |
| audit_score | 15% | value / 100 | auditor, age (max 24 months) |
| years_in_business | 10% | min(value / 10, 1.0) | immer 1.0 |
| sample_test | 5% | 1.0 wenn passed, sonst 0.0 | immer 1.0 |

### Algorithmus

```
Schritt 1: Jedes Signal einzeln normalisieren
           Für jedes vorhandene Signal:
               raw_score = normalize(signal_value)
               confidence = calculate_confidence(signal_metadata)

Schritt 2: Dynamische Gewichtsverteilung
           Wenn Signale fehlen:
               Verteile deren Gewicht auf vorhandene Signale proportional

Schritt 3: Gewichteten Score berechnen
           effective_weight = base_weight * confidence
           weighted_sum = sum(score * effective_weight for all signals)
           total_weight = sum(effective_weight for all signals)
           final_score = weighted_sum / total_weight

Schritt 4: Overall Confidence berechnen
           overall_confidence = sum(confidence * base_weight) / sum(base_weight)
```

### Funktion

```python
def quality_signals_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
    compare_to_original: bool = False
) -> QualitySignalsResult:
    """
    Berechnet Quality Signals Score für einen Kandidaten.
    
    Returns:
        QualitySignalsResult mit score, signals, confidence
    """
```

### Output

```python
@dataclass
class QualitySignalsResult:
    score: float                            # 0.0 bis 1.0
    signals: dict[str, SignalResult]        # Pro-Signal Details
    overall_confidence: float               # 0.0 bis 1.0
    missing_signals: list[str]              # Nicht verfügbare Signale
    risk_factors: list[str]                 # Identifizierte Risiken

@dataclass
class SignalResult:
    score: float | None                     # None wenn nicht verfügbar
    weight_used: float                      # Effektives Gewicht
    confidence: float                       # 0.0 bis 1.0
    notes: str                              # z.B. "Wenige Reviews (45)"
```

### Confidence-Berechnung

```python
def calculate_confidence(signal_name: str, signal_data: dict) -> float:
    confidence = 1.0
    
    # Review Count
    if "review_count" in signal_data:
        min_reviews = 100
        if signal_data["review_count"] < min_reviews:
            confidence *= 0.5 + 0.5 * (signal_data["review_count"] / min_reviews)
    
    # Sample Size
    if "sample_size" in signal_data:
        min_sample = 1000
        if signal_data["sample_size"] < min_sample:
            confidence *= sqrt(signal_data["sample_size"] / min_sample)
    
    # Datenalter
    if "date" in signal_data:
        age_months = calculate_age_months(signal_data["date"])
        if age_months > 24:
            confidence *= max(0.3, 1 - (age_months - 24) / 24)
    
    return clamp(confidence, 0.1, 1.0)
```

## Composite Score

Datei: composite.py

### Zweck

Alle 5 Dimension-Scores zu einem Gesamtscore zusammenführen.

### Formel

```
composite = 0.40 × spec_similarity
          + 0.25 × compliance
          + 0.15 × price_delta
          + 0.10 × lead_time
          + 0.10 × quality_signals
```

### Konfigurierbare Gewichte

Gewichte sind konfigurierbar für verschiedene Prioritäten:

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

### Funktion

```python
def calculate_composite_score(
    dimension_scores: DimensionScores,
    weights: dict[str, float] = None
) -> CompositeResult:
    """
    Berechnet gewichteten Composite Score.
    
    Returns:
        CompositeResult mit score, breakdown, rank_factors
    """
```

## Pipeline

Datei: pipeline.py

### Zweck

Orchestriert die gesamte Scoring-Pipeline: K.O.-Filter, alle 5 Dimensionen, Composite Score, Ranking, Explanations.

### Hauptfunktion

```python
def find_substitutes(
    original: CrawledMaterial,
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements,
    weights: dict[str, float] = None,
    top_n: int = 5
) -> ScoringResult:
    """
    Vollständige Substitution-Scoring-Pipeline.
    
    Args:
        original: Das zu ersetzende Material
        candidates: Alle Kandidaten vom Crawling
        user_requirements: K.O.-Kriterien und Präferenzen
        weights: Optionale custom Gewichte
        top_n: Anzahl Top-Ergebnisse (default 5)
        
    Returns:
        ScoringResult mit top_candidates, rejected, metadata
    """
    
    # Stufe 0: K.O.-Filter
    knockout_result = apply_knockout_filters(candidates, user_requirements)
    
    # Stufe 1 + 2: Scoring für alle passed Kandidaten
    scored_candidates = []
    for kandidat in knockout_result.passed:
        scores = calculate_all_dimensions(original, kandidat, user_requirements)
        composite = calculate_composite_score(scores, weights)
        scored_candidates.append(ScoredCandidate(kandidat, scores, composite))
    
    # Sortieren und Top N
    scored_candidates.sort(key=lambda x: x.composite_score, reverse=True)
    top_candidates = scored_candidates[:top_n]
    
    # Explanations generieren
    for rank, candidate in enumerate(top_candidates, 1):
        candidate.rank = rank
        candidate.explanation = generate_explanation(candidate)
    
    return ScoringResult(
        original=original,
        top_candidates=top_candidates,
        rejected=knockout_result.rejected,
        metadata=ScoringMetadata(weights, len(candidates), ...)
    )
```

## Explanation Generator

### Zweck

Menschenlesbare Erklärungen für jedes Ranking-Ergebnis generieren.

### Struktur

```python
@dataclass
class Explanation:
    summary: str                    # "Exzellente Alternative"
    recommendation: str             # "Empfohlen", "Bedingt empfohlen", "Nicht empfohlen"
    strengths: list[str]            # ["Technisch sehr ähnlich", "Schnell verfügbar"]
    weaknesses: list[str]           # ["Teurer (+18%)"]
    risks: list[str]                # ["Wenig Qualitätsdaten"]
    score_breakdown: dict[str, str] # {"spec": "95%", "compliance": "100%", ...}
```

### Logik

```python
def generate_explanation(scored_candidate: ScoredCandidate) -> Explanation:
    scores = scored_candidate.scores
    composite = scored_candidate.composite_score
    
    # Strengths (score >= 0.8)
    strengths = []
    for dim, score in scores.items():
        if score >= 0.8:
            strengths.append(STRENGTH_MESSAGES[dim])
    
    # Weaknesses (score < 0.5)
    weaknesses = []
    for dim, score in scores.items():
        if score < 0.5:
            weaknesses.append(format_weakness(dim, scored_candidate.details[dim]))
    
    # Summary basierend auf Composite Score
    if composite >= 0.85:
        summary = "Exzellente Alternative"
        recommendation = "Empfohlen"
    elif composite >= 0.70:
        summary = "Gute Alternative"
        recommendation = "Empfohlen"
    elif composite >= 0.55:
        summary = "Akzeptable Alternative"
        recommendation = "Bedingt empfohlen"
    else:
        summary = "Schwache Alternative"
        recommendation = "Nicht empfohlen"
    
    return Explanation(summary, recommendation, strengths, weaknesses, ...)
```

## Testing

### Teststruktur

```
tests/scoring/
├── conftest.py                 # Fixtures, Mock-Daten
├── test_knockout.py            # K.O.-Filter Tests
├── test_spec_similarity.py     # Dimension 1 Tests
├── test_compliance.py          # Dimension 2 Tests
├── test_price_delta.py         # Dimension 3 Tests
├── test_lead_time.py           # Dimension 4 Tests
├── test_quality_signals.py     # Dimension 5 Tests
├── test_composite.py           # Composite Score Tests
├── test_pipeline.py            # Integration Tests
└── test_edge_cases.py          # Edge Cases
```

### Wichtige Test-Szenarien

Knockout:
- Kandidat mit zu hoher MOQ
- Kandidat aus blacklisted Country
- Kandidat ohne critical Certification
- Kandidat der alle Filter besteht

Spec Similarity:
- Identische Materialien (score = 1.0)
- Keine gemeinsamen Properties (score = 0.0)
- Teilweise überlappende Properties
- Properties außerhalb bekannter Ranges

Compliance:
- Perfekter Match
- Teilweiser Match
- Keine Überlappung
- Leere Zertifikat-Listen

Price Delta:
- Günstigerer Kandidat
- Teurerer Kandidat
- Gleicher Preis
- Verschiedene Incoterms
- Mit Tariffs

Lead Time:
- Schnellerer Kandidat
- Langsamerer Kandidat
- Innerhalb Toleranz
- Stock verfügbar (Lead Time = 0)
- Unterschiedliche Reliabilities

Quality Signals:
- Alle Signale verfügbar
- Teilweise Signale
- Keine Signale
- Niedrige Confidence

## Beispiel-Aufruf

```python
from shared.schemas import CrawledMaterial, UserRequirements
from src.scoring.pipeline import find_substitutes

# Original-Material
original = CrawledMaterial(
    id="orig_001",
    name="Aluminium 6061-T6",
    properties={
        "zugfestigkeit": MaterialProperty(value=310, unit="MPa"),
        "dichte": MaterialProperty(value=2.7, unit="g/cm³"),
    },
    certifications=["RoHS", "REACH", "ISO9001"],
    price=PriceInfo(value=3.50, unit="€/kg"),
    lead_time=LeadTimeInfo(days=14, reliability=0.92),
    quality=QualityInfo(supplier_rating={"value": 4.5, "review_count": 200}),
    moq=100,
    country_of_origin="DE",
    incoterm="DDP"
)

# User Requirements
requirements = UserRequirements(
    max_quantity=500,
    destination_country="DE",
    critical_certs=["RoHS"],
    max_lead_time_days=60,
    max_price_multiplier=2.0
)

# Scoring ausführen
result = find_substitutes(
    original=original,
    candidates=crawled_candidates,  # vom Crawling-Modul
    user_requirements=requirements,
    weights=None,  # Default-Gewichte
    top_n=5
)

# Ergebnis
print(f"Top Kandidat: {result.top_candidates[0].kandidat.name}")
print(f"Score: {result.top_candidates[0].composite_score}")
print(f"Empfehlung: {result.top_candidates[0].explanation.recommendation}")
```

## Wichtige Design-Entscheidungen

| Entscheidung | Begründung |
|--------------|------------|
| K.O. vor Scoring | Performance, keine unnötigen Berechnungen |
| Scores zwischen 0 und 1 | Einheitlich, einfach zu gewichten |
| Kein Bonus über 1.0 | Günstigerer Preis oder schnellere Lieferung nicht überbelohnen |
| Confidence bei Quality | Wenig Daten = weniger Gewicht |
| Tolerance bei Lead Time | Kleine Abweichungen ignorieren |
| Dynamische Gewichte | Bei fehlenden Signalen umverteilen |

## Dependencies

```
numpy           # Vektor-Operationen, Cosine Similarity
dataclasses     # Datenstrukturen
typing          # Type Hints
math            # sqrt, etc.
```