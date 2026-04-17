from __future__ import annotations
from dataclasses import dataclass, field

from shared.schemas import BOMContext, BOMEntry, ScoredCandidate

from .evidence import EvidenceType, EvidenceTrail, collect_evidence, build_evidence_trail


@dataclass
class MaterialGroup:
    group_id: str
    material_name: str
    entries: list[BOMEntry]
    companies: list[str]


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
    tradeoffs: list[str]


@dataclass
class ConsolidationResult:
    opportunities: list[ConsolidationOpportunity]
    total_potential_savings: float
    supplier_reduction: int
    evidence_trail: EvidenceTrail


def _get_tier_price(candidate: ScoredCandidate, volume: float) -> float:
    """Gibt den Tier-Preis für ein gegebenes Volumen zurück."""
    tiers = candidate.kandidat.price.tiers
    if not tiers:
        return candidate.kandidat.price.value

    applicable = [t for t in tiers if t.get("min_qty", 0) <= volume]
    if not applicable:
        return candidate.kandidat.price.value
    best = min(applicable, key=lambda t: t.get("price", candidate.kandidat.price.value))
    return best.get("price", candidate.kandidat.price.value)


def _group_similar_materials(
    company_boms: dict[str, list[BOMEntry]],
    similarity_threshold: float = 0.85,
) -> list[MaterialGroup]:
    """
    Gruppiert ähnliche Materialien über mehrere Companies.

    Vereinfachte Implementierung: Materialien mit gleichem Namen werden gruppiert.
    """
    groups: dict[str, MaterialGroup] = {}

    for company, bom_entries in company_boms.items():
        for entry in bom_entries:
            key = entry.material_name.lower().strip()
            if key not in groups:
                groups[key] = MaterialGroup(
                    group_id=key,
                    material_name=entry.material_name,
                    entries=[],
                    companies=[],
                )
            groups[key].entries.append(entry)
            if company not in groups[key].companies:
                groups[key].companies.append(company)

    # Nur Gruppen mit mehreren Companies sind für Konsolidierung interessant
    return [g for g in groups.values() if len(g.companies) > 1]


def calculate_consolidation(
    bom_context: BOMContext,
    scored_candidates: list[ScoredCandidate],
) -> ConsolidationResult:
    """
    Berechnet Konsolidierungs-Potenzial über mehrere Companies.

    Args:
        bom_context: BOM-Daten aller beteiligten Companies
        scored_candidates: Bewertete Kandidaten aus der Scoring-Pipeline

    Returns:
        ConsolidationResult mit Opportunities und Savings
    """
    goals = bom_context.consolidation_goals
    material_groups = _group_similar_materials(bom_context.company_boms)

    evidences = []
    opportunities: list[ConsolidationOpportunity] = []

    for group in material_groups:
        total_volume = sum(e.quantity_per_month for e in group.entries)
        current_total_cost = sum(e.quantity_per_month * e.current_price for e in group.entries)
        current_suppliers = list(set(e.current_supplier for e in group.entries))

        # Kandidaten prüfen die alle beliefern können
        for candidate in scored_candidates:
            # Nur Top-Kandidaten mit ausreichend gutem Score berücksichtigen
            if candidate.composite_score < 0.6:
                continue

            new_price = _get_tier_price(candidate, total_volume)
            new_total_cost = total_volume * new_price

            if current_total_cost == 0:
                continue

            savings_percent = (current_total_cost - new_total_cost) / current_total_cost * 100
            savings_absolute = current_total_cost - new_total_cost

            if savings_percent < goals.min_savings_percent:
                continue

            tradeoffs: list[str] = []
            spec_score = candidate.scores.get("spec", 1.0)
            if spec_score < 1.0:
                tradeoffs.append(
                    f"Companies müssen auf leicht anderen Spec wechseln ({spec_score:.0%} Similarity)"
                )

            ev = collect_evidence(
                field="consolidation_savings",
                value=savings_percent,
                source_type=EvidenceType.CALCULATED,
                metadata={"notes": f"Einsparung durch Konsolidierung: {savings_percent:.1f}%"},
            )
            evidences.append(ev)

            opportunities.append(ConsolidationOpportunity(
                material_group=group,
                recommended_supplier=candidate,
                combined_volume=total_volume,
                savings_percent=round(savings_percent, 2),
                savings_absolute=round(savings_absolute, 2),
                current_supplier_count=len(current_suppliers),
                new_supplier_count=1,
                companies_affected=group.companies,
                tradeoffs=tradeoffs,
            ))

    total_savings = sum(o.savings_percent for o in opportunities)
    supplier_reduction = sum(
        max(0, o.current_supplier_count - o.new_supplier_count) for o in opportunities
    )

    trail = build_evidence_trail("consolidation", evidences, total_expected_fields=len(material_groups))

    return ConsolidationResult(
        opportunities=opportunities,
        total_potential_savings=round(total_savings, 2),
        supplier_reduction=supplier_reduction,
        evidence_trail=trail,
    )
