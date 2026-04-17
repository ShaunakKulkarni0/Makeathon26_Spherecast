from __future__ import annotations
from dataclasses import dataclass

from .evidence import EvidenceTrail
from .uncertainty import UncertaintyReport

from shared.schemas import ScoredCandidate


@dataclass
class StrengthItem:
    text: str
    evidence: str
    confidence: float


@dataclass
class WeaknessItem:
    text: str
    evidence: str
    confidence: float
    mitigation: str | None


@dataclass
class Explanation:
    summary: str
    recommendation: str
    confidence_statement: str

    strengths: list[StrengthItem]
    weaknesses: list[WeaknessItem]
    risks: list[str]

    score_breakdown: dict[str, str]
    evidence_summary: list[str]

    uncertainty_warning: str | None
    verification_needed: list[str]


STRENGTH_MESSAGES = {
    "spec":        "Technische Eigenschaften stimmen sehr gut überein",
    "compliance":  "Alle relevanten Zertifikate vorhanden",
    "price":       "Preis deutlich günstiger als das Original",
    "lead_time":   "Lieferzeit vergleichbar oder besser",
    "quality":     "Hohe Lieferantenqualität nachgewiesen",
}

WEAKNESS_MESSAGES = {
    "spec":       "Technische Abweichungen beim Kandidaten",
    "compliance": "Fehlende Zertifikate beim Kandidaten",
    "price":      "Kandidat deutlich teurer als Original",
    "lead_time":  "Längere Lieferzeit als Original",
    "quality":    "Qualitätssignale unvollständig oder schwach",
}

MITIGATIONS = {
    "price":      "Mengenrabatt verhandeln oder alternative Incoterms prüfen",
    "lead_time":  "Express-Shipping anfragen oder Lagerbestand beim Supplier prüfen",
    "compliance": "Fehlende Zertifikate beim Supplier anfragen",
    "quality":    "Sample-Bestellung zur Qualitätsprüfung anfordern",
    "spec":       "Technische Freigabe durch Engineering einholen",
}


def _summarize_evidence(trail: EvidenceTrail) -> str:
    if not trail.evidences:
        return "Keine Quellenangabe"
    top = trail.evidences[0]
    return f"{top.field} aus {top.source} (Confidence: {top.confidence:.0%})"


def generate_explanation(
    scored_candidate: ScoredCandidate,
    evidence_trails: dict[str, EvidenceTrail],
    uncertainty_report: UncertaintyReport,
) -> Explanation:
    """
    Generiert Explanation mit Evidence und Uncertainty.

    Args:
        scored_candidate: Der bewertete Kandidat
        evidence_trails: Evidence Trail pro Dimension
        uncertainty_report: Uncertainty-Analyse

    Returns:
        Explanation mit Stärken, Schwächen, Risiken und Evidence-Summary
    """
    scores = scored_candidate.scores
    composite = scored_candidate.composite_score
    overall_confidence = uncertainty_report.overall_confidence

    # --- Confidence Statement ---
    if overall_confidence >= 0.8:
        confidence_statement = "Hohe Sicherheit: Diese Empfehlung basiert auf verifizierten Daten."
    elif overall_confidence >= 0.6:
        confidence_statement = "Gute Datenbasis: Die meisten Daten sind verifiziert."
    elif overall_confidence >= 0.4:
        confidence_statement = "Mit Vorbehalt: Einige Daten sollten vor Entscheidung verifiziert werden."
    else:
        confidence_statement = "Niedrige Sicherheit: Empfehlung basiert auf unvollständigen Daten."

    # --- Strengths ---
    strengths: list[StrengthItem] = []
    for dim, score in scores.items():
        if score >= 0.8:
            trail = evidence_trails.get(dim)
            strengths.append(StrengthItem(
                text=STRENGTH_MESSAGES.get(dim, f"{dim}: Guter Score"),
                evidence=_summarize_evidence(trail) if trail else "Keine Quellenangabe",
                confidence=trail.overall_confidence if trail else 0.5,
            ))

    # --- Weaknesses ---
    weaknesses: list[WeaknessItem] = []
    for dim, score in scores.items():
        if score < 0.5:
            trail = evidence_trails.get(dim)
            weaknesses.append(WeaknessItem(
                text=WEAKNESS_MESSAGES.get(dim, f"{dim}: Schwacher Score"),
                evidence=_summarize_evidence(trail) if trail else "Keine Quellenangabe",
                confidence=trail.overall_confidence if trail else 0.5,
                mitigation=MITIGATIONS.get(dim),
            ))

    # --- Evidence Summary ---
    evidence_summary: list[str] = []
    for dim, trail in evidence_trails.items():
        for ev in trail.evidences[:2]:
            evidence_summary.append(f"{dim}: {ev.field} aus {ev.source}")

    # --- Summary und Recommendation ---
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

    if overall_confidence < 0.4 and recommendation == "Empfohlen":
        recommendation = "Bedingt empfohlen (Daten verifizieren)"

    return Explanation(
        summary=summary,
        recommendation=recommendation,
        confidence_statement=confidence_statement,
        strengths=strengths,
        weaknesses=weaknesses,
        risks=uncertainty_report.uncertainty_reasons,
        score_breakdown={dim: f"{score * 100:.0f}%" for dim, score in scores.items()},
        evidence_summary=evidence_summary,
        uncertainty_warning=uncertainty_report.warning_message,
        verification_needed=uncertainty_report.verification_suggestions,
    )
