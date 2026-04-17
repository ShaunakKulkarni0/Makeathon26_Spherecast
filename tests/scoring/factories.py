from __future__ import annotations

from shared.schemas import (
    CrawledMaterial,
    LeadTimeInfo,
    MaterialProperty,
    PriceInfo,
    QualityInfo,
)


def make_quality(
    supplier_rating: dict | None = None,
    defect_rate: dict | None = None,
    on_time_delivery: dict | None = None,
    years_in_business: int | None = 10,
    audit_score: dict | None = None,
) -> QualityInfo:
    return QualityInfo(
        supplier_rating=supplier_rating
        if supplier_rating is not None
        else {"value": 4.2, "review_count": 150},
        defect_rate=defect_rate
        if defect_rate is not None
        else {"value": 1.1, "sample_size": 1200},
        on_time_delivery=on_time_delivery
        if on_time_delivery is not None
        else {"value": 94, "sample_size": 80},
        years_in_business=years_in_business,
        audit_score=audit_score
        if audit_score is not None
        else {"value": 89, "age_months": 8, "passed": True},
    )


def make_material(
    material_id: str,
    name: str | None = None,
    properties: dict[str, MaterialProperty] | None = None,
    certifications: list[str] | None = None,
    price_value: float = 2.0,
    price_unit: str = "EUR/kg",
    price_tiers: list[dict] | None = None,
    lead_days: int = 14,
    lead_reliability: float = 0.9,
    lead_type: str = "standard",
    quality: QualityInfo | None = None,
    moq: int = 100,
    country_of_origin: str = "DE",
    incoterm: str = "DDP",
    source_url: str | None = None,
) -> CrawledMaterial:
    return CrawledMaterial(
        id=material_id,
        name=name or material_id,
        properties=properties
        if properties is not None
        else {
            "zugfestigkeit": MaterialProperty(value=300.0, unit="MPa"),
            "dichte": MaterialProperty(value=1.2, unit="g/cm3"),
        },
        certifications=certifications if certifications is not None else ["RoHS", "ISO9001"],
        price=PriceInfo(value=price_value, unit=price_unit, tiers=price_tiers),
        lead_time=LeadTimeInfo(days=lead_days, reliability=lead_reliability, type=lead_type),
        quality=quality if quality is not None else make_quality(),
        moq=moq,
        country_of_origin=country_of_origin,
        incoterm=incoterm,
        source_url=source_url or f"https://example.com/{material_id}",
    )
