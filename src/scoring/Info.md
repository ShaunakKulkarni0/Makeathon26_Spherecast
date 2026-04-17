# Scoring Modul - Implementierungsstatus


## Inputs und Outputs (allgemein)

### Startpunkt: `find_substitutes(...)`

Die Pipeline startet immer mit:

```python
find_substitutes(
    original: CrawledMaterial,
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements,
    weights: dict[str, float] | None = None,
    top_n: int = 5,
    bom_context: BOMContext | None = None,
) -> ScoringResult
```

### Pflicht-Inputs (ohne diese läuft die Pipeline nicht)

1. `original: CrawledMaterial`
- Das Referenzmaterial, gegen das alle Kandidaten verglichen werden.
- Wichtigste Felder im Vergleich:
- `properties` (für Spec Similarity)
- `certifications` (für Compliance)
- `price` (für Price Delta)
- `lead_time` (für Lead-Time-Vergleich)
- `quality` (für Quality Signals)
- `moq`, `country_of_origin`, `incoterm` (für Knockout + Preis-/Zeit-Adjustments)

2. `candidates: list[CrawledMaterial]`
- Liste aller potenziellen Ersatzmaterialien in derselben Struktur wie `original`.
- Jeder Eintrag wird zuerst durch Knockout gefiltert und danach (falls bestanden) vollständig gescored.
- Leere Liste ist technisch möglich, ergibt aber keine `top_candidates`.

3. `user_requirements: UserRequirements`
- Definiert die harten K.O.-Regeln und den Kontext.
- Felder:
- `destination_country` (relevant für Blacklist + Tariffs)
- `max_quantity` (MOQ-Grenze, optional)
- `critical_certs` (Pflicht-Zertifikate, optional)
- `max_lead_time_days` (harte Lieferzeitgrenze, optional)
- `max_price_multiplier` (Preisgrenze relativ zum Original, Standard `2.0`)

### Optionale Inputs

1. `weights` (optional)
- Wenn `None`, wird Preset `default` verwendet.
- Gewichte steuern die Composite-Berechnung:
- `spec=0.40`, `compliance=0.25`, `price=0.15`, `lead_time=0.10`, `quality=0.10`
- Verfügbare Presets in `shared/constants.py`: `default`, `cost_focused`, `availability_focused`, `quality_focused`.

2. `top_n` (optional, Standard `5`)
- Begrenzung, wie viele Top-Ergebnisse nach dem Ranking zurückgegeben werden.

3. `bom_context` (optional)
- Nur nötig für den Consolidation-Layer (unternehmensübergreifende Einsparpotenziale).
- Wenn `None`, bleibt `consolidation` im Output leer.

### Was innerhalb von `CrawledMaterial` optional sein darf

- `source_url` ist optional.
- `price.tiers` ist optional.
- Viele Felder in `quality` sind optional (`supplier_rating`, `defect_rate`, `on_time_delivery`, `audit_score`, `years_in_business`).
- Fehlende Daten reduzieren i.d.R. Confidence bzw. erzeugen Data Gaps, verhindern aber nicht automatisch das Scoring.

### Output: `ScoringResult`

`find_substitutes(...)` liefert ein Objekt mit:

1. `original`
- Das Originalmaterial (zur Nachvollziehbarkeit im Ergebnis enthalten).

2. `top_candidates: list[ScoredCandidate]`
- Sortiert nach `composite_score` (absteigend), auf `top_n` begrenzt.
- Pro Kandidat enthalten:
- `scores` pro Dimension (`spec`, `compliance`, `price`, `lead_time`, `quality`)
- `composite_score`
- `confidences` + `overall_confidence`
- `evidence_trails`
- `uncertainty_report`
- `rank`
- `explanation`
- `details` (Dimension-spezifische Result-Objekte)

3. `rejected: list[RejectedCandidate]`
- Alle im Knockout ausgeschlossenen Kandidaten inklusive Gründen (`reasons`) und Evidence.

4. `metadata: ScoringMetadata`
- Enthält u.a.:
- verwendete `weights`
- `total_candidates`
- `passed_knockout`
- `average_confidence` der Top-Kandidaten

5. `consolidation` (optional)
- Nur gesetzt, wenn `bom_context` übergeben wurde.
- Sonst `None`.

## Scoring Data Flow (ASCII)

```text
SCORING DATA FLOW (src/scoring)

Input:
  original: CrawledMaterial
  candidates: list[CrawledMaterial]
  user_requirements: UserRequirements
  weights?: dict[str,float]
  top_n: int
  bom_context?: BOMContext

                         +--------------------------------------+
                         | find_substitutes(...)                |
                         +-------------------+------------------+
                                             |
                                             v
                         +--------------------------------------+
                         | apply_knockout_filters(...)          |
                         | - MOQ                                |
                         | - country blacklist                  |
                         | - critical_certs                     |
                         | - max_lead_time                      |
                         | - max_price_multiplier               |
                         | uses collect_evidence(...)           |
                         +-------------------+------------------+
                                             |
                       +---------------------+----------------------+
                       |                                            |
                       v                                            v
         passed candidates                                   rejected candidates
                       |
                       v
      For each passed candidate (5D scoring):
                       |
      +----------------+----------------+----------------+----------------+----------------+
      |                |                |                |                |
      v                v                v                v                v
+-----------+   +-------------+   +-------------+   +-------------+   +------------------+
| spec_     |   | compliance_ |   | price_delta |   | lead_time   |   | quality_signals  |
| similarity|   | score       |   | _score      |   | _score      |   | _score           |
+-----+-----+   +------+------+   +------+------+   +------+------+   +---------+--------+
      |                |                |                |                          |
      | _normalize()   |                | _get_tier_price| _determine_risk_level()  |
      | _cosine_       |                |                |                          |
      | similarity()   |                |                |                          |
      +-------- uses collect_evidence(...) + build_evidence_trail(...) ------------+

                       |
                       v
      assemble:
        scores
        confidences
        evidence_trails
        details

                       |
          +------------+-------------------+
          |                                |
          v                                v
+---------------------------+    +------------------------------+
| calculate_composite_score |    | generate_uncertainty_report  |
+---------------------------+    +------------------------------+
                                               |
                                               v
                                confidence_to_uncertainty(...)

                       |
                       v
               ScoredCandidate(...)

After all candidates:
  - sort by composite_score desc
  - take top_n
  - set rank
  - generate_explanation(...) per top candidate
      -> _summarize_evidence(...)

Optional BOM layer:
  if bom_context:
    calculate_consolidation(...)
      -> _group_similar_materials(...)
      -> _get_tier_price(...)
      -> collect_evidence(...)
      -> build_evidence_trail(...)

Output:
  ScoringResult(
    original,
    top_candidates (with explanation),
    rejected,
    metadata,
    consolidation? )

Note:
  calculate_uncertainty_adjusted_score(...) exists in uncertainty.py,
  but is currently not called by find_substitutes(...).
```
