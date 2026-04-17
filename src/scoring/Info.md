# Scoring Modul - Implementierungsstatus

## Neue Dateien

| Datei | Inhalt |
|-------|--------|
| `evidence.py` | Definiert Evidence, EvidenceTrail, EvidenceType — das System das dokumentiert woher jede Information stammt, inkl. automatischer Confidence-Berechnung je nach Quelle |
| `uncertainty.py` | UncertaintyReport — bewertet wie sicher eine Empfehlung ist, generiert Warnungen und Verification-Suggestions wenn Confidence zu niedrig |
| `explanation.py` | Generiert menschenlesbare Erklärungen pro Kandidat mit Stärken, Schwächen, Mitigations und Evidence-Summary |
| `consolidation.py` | BOM-Konsolidierungs-Layer — erkennt wenn mehrere Companies ähnliche Materialien kaufen und berechnet Einsparungspotenzial durch gemeinsamen Lieferanten |

## Bestehende Dateien (jetzt mit Inhalt)

| Datei | Inhalt |
|-------|--------|
| `knockout.py` | Filtert Kandidaten nach MOQ, Blacklist, fehlenden Critical Certs, Lead Time und Preis — mit Evidence pro Ablehnungsgrund |
| `spec_similarity.py` | Cosine Similarity auf normalisierten Property-Vektoren, sammelt Evidence pro verglichener Property |
| `compliance.py` | Set-Intersection der Zertifikate, unterscheidet zwischen verifizierten (offizielle DB) und nur behaupteten Certs |
| `price_delta.py` | Preisvergleich inkl. Incoterm-Aufschlag und Zollsätzen, jeder Adjustment-Schritt hat eigene Evidence |
| `lead_time.py` | Lieferzeitvergleich mit Reliability-Faktor, Lagerbestand-Check und Risk Level |
| `quality_signals.py` | 6 Qualitätssignale (Rating, Defektrate, Pünktlichkeit, Audit, Jahre, Sample) mit dynamischen Gewichten wenn Daten fehlen |
| `composite.py` | Confidence-gewichteter Gesamtscore: Σ(weight × score × confidence) / Σ(weight × confidence) |
| `pipeline.py` | Orchestriert alle 4 Stufen: KO-Filter → 5D Scoring → Composite+Uncertainty → BOM Consolidation |
| `__init__.py` | Exports aller öffentlichen Klassen und Funktionen |



## Pflicht-Eingaben

### 1. `CrawledMaterial` — das Original
```python
CrawledMaterial(
    id, name,
    properties,        # dict: {"zugfestigkeit": MaterialProperty(310, "MPa"), ...}
    certifications,    # list: ["RoHS", "ISO9001"]
    price,             # PriceInfo(value, unit, tiers?)
    lead_time,         # LeadTimeInfo(days, reliability, type)
    quality,           # QualityInfo(supplier_rating?, defect_rate?, ...)
    moq, country_of_origin, incoterm
)
```

### 2. `list[CrawledMaterial]` — die Kandidaten
Gleiche Struktur, beliebig viele.

### 3. `UserRequirements` — die K.O.-Kriterien
```python
UserRequirements(
    destination_country="DE",     # Pflicht für Blacklist + Tariffs
    max_quantity=None,            # Optional: MOQ-Check
    critical_certs=None,          # Optional: z.B. ["FDA"]
    max_lead_time_days=None,      # Optional
    max_price_multiplier=2.0,     # Standard: bis 2x Originalpreis erlaubt
)
```

## Was optional ist

| Parameter | Standard | Wofür |
|-----------|----------|-------|
| `weights` | `default` (40/25/15/10/10) | Andere Gewichtung z.B. `cost_focused` |
| `top_n` | 5 | Wie viele Top-Kandidaten |
| `bom_context` | `None` | Nur wenn BOM-Konsolidierung gewünscht |
