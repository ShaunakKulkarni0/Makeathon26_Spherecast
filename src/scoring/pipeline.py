from __future__ import annotations

from shared.schemas import (
    CrawledMaterial,
    UserRequirements,
    ScoredCandidate,
    ScoringResult,
    ScoringMetadata,
    BOMContext,
)
from shared.constants import WEIGHT_PRESETS, DEFAULT_TOP_N

from .knockout import apply_knockout_filters
from .spec_similarity import spec_similarity
from .compliance import compliance_score
from .price_delta import price_delta_score
from .lead_time import lead_time_score
from .quality_signals import quality_signals_score
from .composite import calculate_composite_score
from .uncertainty import generate_uncertainty_report
from .explanation import generate_explanation
from .consolidation import calculate_consolidation


def find_substitutes(
    original: CrawledMaterial,
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements,
    weights: dict[str, float] | None = None,
    top_n: int = DEFAULT_TOP_N,
    bom_context: BOMContext | None = None,
) -> ScoringResult:
    """
    Vollständige Substitution-Scoring-Pipeline mit Evidence und Uncertainty.

    Stufe 0: K.O.-Filter
    Stufe 1: 5D Scoring + Evidence Collection
    Stufe 2: Composite Score + Uncertainty
    Stufe 3: BOM Consolidation (optional)

    Args:
        original: Das zu ersetzende Material
        candidates: Alle potenziellen Ersatzmaterialien
        user_requirements: K.O.-Kriterien und Zielland
        weights: Optionale Gewichte für die 5 Dimensionen
        top_n: Anzahl Top-Kandidaten im Ergebnis
        bom_context: Optional für BOM-Konsolidierungs-Layer

    Returns:
        ScoringResult mit Top-Kandidaten, Rejected, Metadata und optionalem Consolidation
    """
    effective_weights = weights or WEIGHT_PRESETS["default"]

    # --- Stufe 0: K.O.-Filter ---
    knockout_result = apply_knockout_filters(candidates, user_requirements, original)

    # --- Stufe 1+2: Scoring mit Evidence Collection ---
    scored_candidates: list[ScoredCandidate] = []
    may_contain_hits = knockout_result.allergen_may_contain_hits

    for kandidat in knockout_result.passed:
        spec_result = spec_similarity(original, kandidat)
        compliance_result = compliance_score(original, kandidat)
        price_result = price_delta_score(original, kandidat, user_requirements)
        lead_result = lead_time_score(original, kandidat)
        quality_result = quality_signals_score(original, kandidat)

        scores = {
            "spec":        spec_result.score,
            "compliance":  compliance_result.score,
            "price":       price_result.score,
            "lead_time":   lead_result.score,
            "quality":     quality_result.score,
        }

        confidences = {
            "spec":        spec_result.confidence,
            "compliance":  compliance_result.confidence,
            "price":       price_result.confidence,
            "lead_time":   lead_result.confidence,
            "quality":     quality_result.confidence,
        }

        evidence_trails = {
            "spec":        spec_result.evidence_trail,
            "compliance":  compliance_result.evidence_trail,
            "price":       price_result.evidence_trail,
            "lead_time":   lead_result.evidence_trail,
            "quality":     quality_result.evidence_trail,
        }

        details = {
            "spec":        spec_result,
            "compliance":  compliance_result,
            "price":       price_result,
            "lead_time":   lead_result,
            "quality":     quality_result,
        }

        composite = calculate_composite_score(scores, confidences, effective_weights)
        risk_hits = may_contain_hits.get(kandidat.id, [])
        risk_penalty = min(0.25, 0.10 * len(risk_hits))
        adjusted_composite_score = round(max(0.0, composite.score - risk_penalty), 4)

        uncertainty = generate_uncertainty_report(scores, evidence_trails, effective_weights)
        if risk_hits:
            uncertainty.uncertainty_reasons.append(
                f"allergen: moegliche Spuren von {', '.join(risk_hits)}"
            )
            uncertainty.verification_suggestions.append(
                "Allergen-/Spurenstatement und COA vor Freigabe verifizieren"
            )
            if not uncertainty.warning_message:
                uncertainty.warning_message = (
                    "Allergen-Hinweis erkannt: moegliche Spuren vorhanden. "
                    "Vor Entscheidung pruefen."
                )

        scored_candidates.append(ScoredCandidate(
            kandidat=kandidat,
            scores=scores,
            composite_score=adjusted_composite_score,
            confidences=confidences,
            overall_confidence=composite.confidence,
            evidence_trails=evidence_trails,
            uncertainty_report=uncertainty,
            details={
                **details,
                "allergen_risk": {
                    "may_contain_hits": risk_hits,
                    "penalty_applied": risk_penalty,
                },
            },
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
            candidate.uncertainty_report,
        )

    # --- Stufe 3: BOM Consolidation (optional) ---
    consolidation = None
    if bom_context:
        consolidation = calculate_consolidation(bom_context, scored_candidates)

    avg_confidence = (
        sum(c.overall_confidence for c in top_candidates) / len(top_candidates)
        if top_candidates else 0.0
    )

    return ScoringResult(
        original=original,
        top_candidates=top_candidates,
        rejected=knockout_result.rejected,
        metadata=ScoringMetadata(
            weights=effective_weights,
            total_candidates=len(candidates),
            passed_knockout=len(knockout_result.passed),
            average_confidence=round(avg_confidence, 3),
        ),
        consolidation=consolidation,
    )
