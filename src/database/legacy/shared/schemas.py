"""
shared/schemas.py
Pydantic models that are the single source of truth for data flowing through
Layer 1 (normalization) and Layer 2 (embedding + matching).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Layer 1 enumerations
# ---------------------------------------------------------------------------

class SKUCategory(str, Enum):
    CHEMICAL      = "Chemical"
    BOTANICAL     = "Botanical"
    BIOACTIVE     = "Bioactive"
    BRANDED       = "Branded"
    EXCIPIENT     = "Excipient"
    FLAVOR_COLOR  = "Flavor/Color"
    BLEND_PREMIX  = "Blend/Premix"
    UNKNOWN       = "Unknown"


# ---------------------------------------------------------------------------
# Layer 1 output
# ---------------------------------------------------------------------------

class ExtractedEntities(BaseModel):
    cas_number:              Optional[str] = None
    dosage_or_concentration: Optional[str] = None
    chiral_form:             Optional[str] = None


class NormalizationResult(BaseModel):
    """
    The structured object returned by the LLM normalization call (Layer 1).
    Maps 1-to-1 to the JSON schema the LLM is instructed to produce.
    """
    category:          SKUCategory
    extracted_entities: ExtractedEntities
    canonical_string:  str = Field(
        ...,
        description="Continuous natural-language paragraph describing the material.",
    )

    # Convenience: the raw sku_id / sku_name are attached after the LLM call
    sku_id:   Optional[int] = None
    sku_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Layer 2 enumerations
# ---------------------------------------------------------------------------

class ConfidenceLevel(str, Enum):
    EXACT       = "Exact"
    FUNCTIONAL  = "Functional"
    CATEGORY    = "Category"
    NO_MATCH    = "No Match"


class ComplianceFlag(str, Enum):
    VEGAN_CONFLICT          = "VEGAN_CONFLICT"
    BIOAVAILABILITY_DELTA   = "BIOAVAILABILITY_DELTA"
    LABELING_CLAIM_IMPACT   = "LABELING_CLAIM_IMPACT"
    BRANDED_NO_SUB          = "BRANDED_NO_SUB"


# ---------------------------------------------------------------------------
# Layer 2 output
# ---------------------------------------------------------------------------

class JudgeResult(BaseModel):
    """
    The structured object returned by the LLM judge call (Layer 2, step 2.3).
    """
    confidence_level: ConfidenceLevel
    reasoning:        str
    compliance_flags: list[ComplianceFlag] = Field(default_factory=list)

    # Populated by the pipeline after the LLM call
    sku_id_a:          Optional[int]   = None
    sku_id_b:          Optional[int]   = None
    cosine_similarity: Optional[float] = None


class VectorRecord(BaseModel):
    """A SKU's embedding stored in the vector DB."""
    sku_id:    int
    embedding: list[float] = Field(..., description="3072-dim vector from text-embedding-3-large")