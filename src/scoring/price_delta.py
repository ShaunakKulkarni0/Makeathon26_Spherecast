from __future__ import annotations
from dataclasses import dataclass

from shared.schemas import CrawledMaterial, UserRequirements
from shared.constants import INCOTERM_ADJUSTMENTS, TARIFF_RATES

from .evidence import Evidence, EvidenceType, EvidenceTrail, collect_evidence, build_evidence_trail


@dataclass
class PriceAdjustment:
    type: str           # "incoterm", "tariff", "tier"
    description: str
    amount: float
    evidence: Evidence


@dataclass
class PriceDeltaResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail

    delta_percent: float
    delta_absolute: float
    direction: str      # "cheaper", "equal", "more_expensive"
    original_price: float
    kandidat_price: float
    unit: str

    adjustments: list[PriceAdjustment]


def _get_tier_price(price_value: float, tiers: list[dict] | None, quantity: int | None) -> float:
    """Gibt den günstigsten Tier-Preis zurück, wenn Mengenrabatte vorhanden und Menge bekannt."""
    if not tiers or quantity is None:
        return price_value
    applicable = [t for t in tiers if t.get("min_qty", 0) <= quantity]
    if not applicable:
        return price_value
    best = min(applicable, key=lambda t: t.get("price", price_value))
    return best.get("price", price_value)


def price_delta_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
    user_requirements: UserRequirements | None = None,
    max_penalty_percent: float = 50.0,
) -> PriceDeltaResult:
    """
    Berechnet Price Delta Score mit Evidence Trail.

    Berücksichtigt Incoterms, Tariffs und Price Tiers.

    Args:
        original: Das Original-Material
        kandidat: Der potenzielle Ersatz
        user_requirements: Für Zielland und max. Menge
        max_penalty_percent: Ab dieser Abweichung ist der Score = 0

    Returns:
        PriceDeltaResult mit Score, Confidence und Adjustments
    """
    destination = (user_requirements.destination_country if user_requirements else "DE")
    quantity = (user_requirements.max_quantity if user_requirements else None)

    evidences: list[Evidence] = []
    adjustments: list[PriceAdjustment] = []

    # --- Original Preis ---
    orig_base = _get_tier_price(original.price.value, original.price.tiers, quantity)
    orig_ev = collect_evidence(
        field="price",
        value=orig_base,
        source_type=EvidenceType.SUPPLIER_DATABASE,
        source_url=original.source_url,
        metadata={"notes": "Original-Material Basispreis"},
    )
    evidences.append(orig_ev)

    # --- Kandidat Preis ---
    kand_base = _get_tier_price(kandidat.price.value, kandidat.price.tiers, quantity)
    kand_ev = collect_evidence(
        field="price",
        value=kand_base,
        source_type=EvidenceType.SUPPLIER_DATABASE,
        source_url=kandidat.source_url,
    )
    evidences.append(kand_ev)

    adjusted_original = orig_base
    adjusted_kandidat = kand_base

    # --- Incoterm-Adjustments ---
    orig_incoterm = INCOTERM_ADJUSTMENTS.get(original.incoterm, INCOTERM_ADJUSTMENTS["DDP"])
    kand_incoterm = INCOTERM_ADJUSTMENTS.get(kandidat.incoterm, INCOTERM_ADJUSTMENTS["DDP"])

    orig_inco_add = orig_base * orig_incoterm["cost_adder"]
    kand_inco_add = kand_base * kand_incoterm["cost_adder"]

    adjusted_original += orig_inco_add
    adjusted_kandidat += kand_inco_add

    if kand_inco_add != 0:
        inco_ev = collect_evidence(
            field="incoterm_adjustment",
            value=kand_inco_add,
            source_type=EvidenceType.CALCULATED,
            metadata={"notes": f"Incoterm {kandidat.incoterm}: +{kand_incoterm['cost_adder']*100:.0f}% geschätzte Shipping-Kosten"},
        )
        evidences.append(inco_ev)
        adjustments.append(PriceAdjustment(
            type="incoterm",
            description=f"{kand_incoterm['description']} ({kandidat.incoterm})",
            amount=kand_inco_add,
            evidence=inco_ev,
        ))

    # --- Tariff-Adjustments ---
    tariff_key = (kandidat.country_of_origin, destination)
    tariff_rate = TARIFF_RATES.get(tariff_key, 0.0)
    tariff_amount = adjusted_kandidat * tariff_rate

    if tariff_rate > 0:
        adjusted_kandidat += tariff_amount
        tariff_ev = collect_evidence(
            field="tariff",
            value=tariff_rate,
            source_type=EvidenceType.EXTERNAL_API,
            metadata={"notes": f"Zollsatz {kandidat.country_of_origin}→{destination}: {tariff_rate*100:.0f}%"},
        )
        evidences.append(tariff_ev)
        adjustments.append(PriceAdjustment(
            type="tariff",
            description=f"Zoll {kandidat.country_of_origin}→{destination}",
            amount=tariff_amount,
            evidence=tariff_ev,
        ))

    # --- Score Berechnung ---
    if adjusted_original == 0:
        score = 0.0
        delta_percent = 0.0
    else:
        delta_percent = ((adjusted_kandidat - adjusted_original) / adjusted_original) * 100
        if delta_percent <= 0:
            score = 1.0
        else:
            score = max(0.0, 1.0 - (delta_percent / max_penalty_percent))

    delta_absolute = adjusted_kandidat - adjusted_original
    direction = (
        "cheaper" if delta_percent < -1
        else "equal" if abs(delta_percent) <= 1
        else "more_expensive"
    )

    trail = build_evidence_trail("price_delta", evidences, total_expected_fields=3)

    calculated_count = sum(1 for ev in evidences if ev.type == EvidenceType.CALCULATED)
    if evidences:
        confidence = trail.overall_confidence * (1 - 0.1 * calculated_count / len(evidences))
    else:
        confidence = 0.5

    return PriceDeltaResult(
        score=round(score, 4),
        confidence=round(confidence, 3),
        evidence_trail=trail,
        delta_percent=round(delta_percent, 2),
        delta_absolute=round(delta_absolute, 4),
        direction=direction,
        original_price=adjusted_original,
        kandidat_price=adjusted_kandidat,
        unit=kandidat.price.unit,
        adjustments=adjustments,
    )
