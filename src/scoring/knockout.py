from __future__ import annotations
from dataclasses import dataclass, field

from shared.schemas import CrawledMaterial, RejectedCandidate, UserRequirements
from shared.constants import COUNTRY_BLACKLIST, MAX_KNOCKOUT_CANDIDATES

from .evidence import Evidence, EvidenceType, collect_evidence


@dataclass
class KnockoutResult:
    passed: list[CrawledMaterial]
    rejected: list[RejectedCandidate]
    allergen_may_contain_hits: dict[str, list[str]] = field(default_factory=dict)


_ALLERGEN_ALIASES: dict[str, str] = {
    "nut": "tree_nuts",
    "nuts": "tree_nuts",
    "almond": "tree_nuts",
    "walnut": "tree_nuts",
    "hazelnut": "tree_nuts",
    "cashew": "tree_nuts",
    "pistachio": "tree_nuts",
    "peanut": "peanuts",
    "peanuts": "peanuts",
    "milk": "milk",
    "dairy": "milk",
    "egg": "egg",
    "eggs": "egg",
    "soy": "soy",
    "soya": "soy",
    "gluten": "wheat_gluten",
    "wheat": "wheat_gluten",
    "sesame": "sesame",
    "mustard": "mustard",
    "celery": "celery",
    "fish": "fish",
    "crustacean": "crustaceans",
    "crustaceans": "crustaceans",
    "mollusc": "molluscs",
    "molluscs": "molluscs",
    "lupin": "lupin",
    "sulphite": "sulphites",
    "sulfite": "sulphites",
}


def _canonicalize_allergen(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _ALLERGEN_ALIASES.get(normalized, normalized)


def _canonicalize_allergens(values: list[str] | None) -> set[str]:
    if not values:
        return set()
    return {_canonicalize_allergen(v) for v in values if isinstance(v, str) and v.strip()}


def apply_knockout_filters(
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements,
    original: CrawledMaterial | None = None,
) -> KnockoutResult:
    """
    Filtert Kandidaten nach harten K.O.-Kriterien.
    Dokumentiert Evidence für jede Entscheidung.

    Args:
        candidates: Alle potenziellen Ersatzmaterialien
        user_requirements: Harte Ausschlusskriterien vom User
        original: Das Original-Material (für Preis-Vergleich)

    Returns:
        KnockoutResult mit passed- und rejected-Liste
    """
    passed: list[CrawledMaterial] = []
    rejected: list[RejectedCandidate] = []

    destination = user_requirements.destination_country
    blacklist = COUNTRY_BLACKLIST.get(destination, [])
    critical_certs = set(user_requirements.critical_certs or [])
    prohibited_allergens = _canonicalize_allergens(user_requirements.prohibited_allergens)

    original_price = original.price.value if original else None
    max_price = (
        original_price * user_requirements.max_price_multiplier
        if original_price is not None
        else None
    )

    allergen_may_contain_hits: dict[str, list[str]] = {}

    for candidate in candidates:
        reasons: list[str] = []
        evidences: list[Evidence] = []
        candidate_allergens = candidate.allergen_profile
        candidate_contains = _canonicalize_allergens(candidate_allergens.contains)
        candidate_may_contain = _canonicalize_allergens(candidate_allergens.may_contain)

        # --- MOQ Check ---
        if (
            user_requirements.max_quantity is not None
            and candidate.moq > user_requirements.max_quantity
        ):
            reasons.append(
                f"MOQ {candidate.moq} > Max-Menge {user_requirements.max_quantity}"
            )
            evidences.append(
                collect_evidence(
                    field="moq",
                    value=candidate.moq,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": f"MOQ überschreitet User-Maximum von {user_requirements.max_quantity}"},
                )
            )

        # --- Blacklist Check ---
        if candidate.country_of_origin in blacklist:
            reasons.append(
                f"Herkunftsland {candidate.country_of_origin} auf Blacklist für {destination}"
            )
            evidences.append(
                collect_evidence(
                    field="country_of_origin",
                    value=candidate.country_of_origin,
                    source_type=EvidenceType.EXTERNAL_API,
                    metadata={"notes": "Sanktionsliste / Blacklist-Prüfung"},
                )
            )

        # --- Critical Certifications Check ---
        candidate_certs = set(candidate.certifications)
        missing_certs = critical_certs - candidate_certs
        if missing_certs:
            reasons.append(f"Kritische Zertifikate fehlen: {', '.join(sorted(missing_certs))}")
            for cert in missing_certs:
                evidences.append(
                    collect_evidence(
                        field="certification",
                        value=None,
                        source_type=EvidenceType.CERTIFICATION_DB,
                        metadata={"notes": f"Keine {cert}-Registrierung gefunden für {candidate.name}"},
                    )
                )

        # --- Max Lead Time Check ---
        if (
            user_requirements.max_lead_time_days is not None
            and candidate.lead_time.days > user_requirements.max_lead_time_days
        ):
            reasons.append(
                f"Lieferzeit {candidate.lead_time.days} Tage > Maximum {user_requirements.max_lead_time_days} Tage"
            )
            evidences.append(
                collect_evidence(
                    field="lead_time",
                    value=candidate.lead_time.days,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": "Lieferzeit überschreitet User-Maximum"},
                )
            )

        # --- Max Price Check ---
        if max_price is not None and candidate.price.value > max_price:
            reasons.append(
                f"Preis {candidate.price.value} {candidate.price.unit} > Maximum {max_price:.2f}"
            )
            evidences.append(
                collect_evidence(
                    field="price",
                    value=candidate.price.value,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": f"Preis überschreitet {user_requirements.max_price_multiplier}x Original"},
                )
            )

        # --- Allergen Contains Check (hard KO) ---
        contains_hits = sorted(candidate_contains & prohibited_allergens)
        if contains_hits:
            reasons.append(f"Verbotene Allergene enthalten: {', '.join(contains_hits)}")
            evidences.append(
                collect_evidence(
                    field="allergens.contains",
                    value=contains_hits,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": "Direkter Treffer in 'contains' gegen prohibited_allergens"},
                )
            )

        # --- Allergen May-Contain Check (risk flag for downstream penalty) ---
        may_contain_hits = sorted(candidate_may_contain & prohibited_allergens)
        if may_contain_hits:
            allergen_may_contain_hits[candidate.id] = may_contain_hits
            evidences.append(
                collect_evidence(
                    field="allergens.may_contain",
                    value=may_contain_hits,
                    source_type=EvidenceType.SUPPLIER_WEBSITE,
                    metadata={"notes": "Spuren-Hinweis fuer Risiko-Penalty im Ranking"},
                )
            )

        if reasons:
            rejected.append(RejectedCandidate(
                candidate=candidate,
                reasons=reasons,
                evidence=evidences,
            ))
        else:
            passed.append(candidate)

    # Limit auf MAX_KNOCKOUT_CANDIDATES
    passed = passed[:MAX_KNOCKOUT_CANDIDATES]

    return KnockoutResult(
        passed=passed,
        rejected=rejected,
        allergen_may_contain_hits=allergen_may_contain_hits,
    )
