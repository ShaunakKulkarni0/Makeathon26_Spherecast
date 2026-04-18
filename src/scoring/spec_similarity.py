from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass

from shared.schemas import CrawledMaterial

from .evidence import Evidence, EvidenceTrail, EvidenceType, build_evidence_trail, collect_evidence


EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_CACHE: dict[str, list[float]] = {}


@dataclass
class SemanticComparison:
    original_text_hash: str
    kandidat_text_hash: str
    original_text_length: int
    kandidat_text_length: int
    original_text_preview: str
    kandidat_text_preview: str
    original_embedding_cached: bool
    kandidat_embedding_cached: bool
    original_evidence: Evidence
    kandidat_evidence: Evidence


@dataclass
class SpecSimilarityResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail

    common_props: list[str]
    missing_in_kandidat: list[str]
    extra_in_kandidat: list[str]
    details: dict[str, SemanticComparison]


_SYNONYMS: dict[str, list[str]] = {
    "glucose": ["dextrose", "traubenzucker"],
    "dextrose": ["glucose", "traubenzucker"],
    "traubenzucker": ["glucose", "dextrose"],
    "sucrose": ["saccharose", "table sugar", "haushaltszucker"],
    "saccharose": ["sucrose", "haushaltszucker"],
    "fructose": ["fruchtzucker"],
    "maltodextrin": ["glucose polymer", "de carrier"],
    "erythritol": ["zuckeralkohol"],
    "xylitol": ["birkenzucker", "zuckeralkohol"],
    "stevia": ["steviol glycosides", "natuerlicher suessstoff"],
    "allulose": ["psicose"],
}

_FUNCTION_TAGS: dict[str, str] = {
    "sweet": "sweetener",
    "sugar": "sweetener",
    "suess": "sweetener",
    "dextrose": "carbohydrate energy source",
    "glucose": "carbohydrate energy source",
    "maltodextrin": "carrier and carbohydrate energy source",
    "fiber": "texture and dietary fiber support",
    "inulin": "fiber and prebiotic function",
    "electrolyte": "hydration support",
    "protein": "protein supplementation",
}


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x**2 for x in a))
    mag_b = math.sqrt(sum(x**2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _extract_synonyms(name: str) -> list[str]:
    lowered = name.lower()
    found: list[str] = []
    for key, synonyms in _SYNONYMS.items():
        if key in lowered:
            found.extend(synonyms)
    return sorted(set(found))


def _extract_function_tags(name: str, properties: dict[str, object]) -> list[str]:
    lowered = name.lower()
    tags: list[str] = []
    for key, fn in _FUNCTION_TAGS.items():
        if key in lowered:
            tags.append(fn)

    prop_keys = " ".join(properties.keys()).lower()
    if "glycemic" in prop_keys:
        tags.append("metabolic response relevance")
    if "sweetness" in prop_keys:
        tags.append("sweetening intensity")
    if "purity" in prop_keys:
        tags.append("quality and standardization")
    if "particle" in prop_keys:
        tags.append("processing and solubility behavior")
    return sorted(set(tags))


def _derive_category(name: str) -> str:
    lowered = name.lower()
    if any(k in lowered for k in ("sugar", "sucrose", "fructose", "glucose", "dextrose")):
        return "sweetener / sugar ingredient"
    if any(k in lowered for k in ("erythritol", "xylitol", "sorbitol", "mannitol", "isomalt")):
        return "polyol sweetener"
    if any(k in lowered for k in ("stevia", "sucralose", "allulose", "tagatose")):
        return "high-intensity or low-glycemic sweetener"
    if any(k in lowered for k in ("protein", "whey", "casein")):
        return "protein supplement ingredient"
    return "supplement / food ingredient"


def material_to_text(material: CrawledMaterial) -> str:
    """
    Build a semantic material description for embedding comparison.

    Includes: name, synonyms, function, properties, category and short description.
    """
    synonyms = _extract_synonyms(material.name)
    function_tags = _extract_function_tags(material.name, material.properties)
    category = _derive_category(material.name)

    properties_txt = ", ".join(
        f"{k}={v.value} {v.unit}" for k, v in sorted(material.properties.items())
    )
    certs_txt = ", ".join(sorted(material.certifications)) if material.certifications else "none"

    description = (
        f"Ingredient {material.name} sourced from {material.country_of_origin}; "
        f"incoterm {material.incoterm}; MOQ {material.moq}; "
        f"price {material.price.value} {material.price.unit}; "
        f"lead time {material.lead_time.days} days ({material.lead_time.type})."
    )

    lines = [
        f"name: {material.name}",
        f"category: {category}",
        f"synonyms: {', '.join(synonyms) if synonyms else 'none'}",
        f"function: {', '.join(function_tags) if function_tags else 'general ingredient'}",
        f"properties: {properties_txt}",
        f"certifications: {certs_txt}",
        f"description: {description}",
    ]
    return "\n".join(lines)


def _load_client():
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "python-dotenv is required for semantic spec similarity. Install dependencies first."
        ) from exc
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for embedding-based spec similarity.") from exc

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Set it in .env (OPENAI_API_KEY=...) before scoring."
        )

    return OpenAI(api_key=api_key)


def _get_embedding(text: str) -> tuple[list[float], bool]:
    key = _text_hash(text)
    if key in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[key], True

    client = _load_client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    embedding = list(response.data[0].embedding)
    _EMBEDDING_CACHE[key] = embedding
    return embedding, False


def _text_quality_confidence(material_text: str, material: CrawledMaterial) -> float:
    words = len(material_text.split())
    properties_count = len(material.properties)
    cert_count = len(material.certifications)

    score = 0.35
    score += min(words / 160.0, 0.25)
    score += min(properties_count / 8.0, 0.2)
    score += min(cert_count / 6.0, 0.1)
    if _extract_synonyms(material.name):
        score += 0.05
    if _extract_function_tags(material.name, material.properties):
        score += 0.05

    return max(0.0, min(1.0, score))


def spec_similarity(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
) -> SpecSimilarityResult:
    """
    Semantic spec similarity using OpenAI embeddings.
    Optimized for supplements/food ingredient substitution semantics.
    """
    orig_keys = set(original.properties.keys())
    kand_keys = set(kandidat.properties.keys())
    common = sorted(orig_keys & kand_keys)
    missing_in_kandidat = sorted(orig_keys - kand_keys)
    extra_in_kandidat = sorted(kand_keys - orig_keys)

    original_text = material_to_text(original)
    kandidat_text = material_to_text(kandidat)

    original_embedding, original_cached = _get_embedding(original_text)
    kandidat_embedding, kandidat_cached = _get_embedding(kandidat_text)
    score = _cosine_similarity(original_embedding, kandidat_embedding)

    original_hash = _text_hash(original_text)
    kandidat_hash = _text_hash(kandidat_text)

    orig_ev = collect_evidence(
        field="semantic_embedding",
        value={"text_hash": original_hash, "model": EMBEDDING_MODEL},
        source_type=EvidenceType.EXTERNAL_API,
        source_url="openai://embeddings",
        metadata={
            "notes": "Semantic embedding for original material",
            "sample_size": len(original_text.split()),
        },
    )
    kand_ev = collect_evidence(
        field="semantic_embedding",
        value={"text_hash": kandidat_hash, "model": EMBEDDING_MODEL},
        source_type=EvidenceType.EXTERNAL_API,
        source_url="openai://embeddings",
        metadata={
            "notes": "Semantic embedding for candidate material",
            "sample_size": len(kandidat_text.split()),
        },
    )
    trail = build_evidence_trail(
        "spec_similarity",
        [orig_ev, kand_ev],
        total_expected_fields=2,
    )

    quality_conf = (
        _text_quality_confidence(original_text, original)
        + _text_quality_confidence(kandidat_text, kandidat)
    ) / 2.0
    confidence = (trail.overall_confidence * 0.6) + (quality_conf * 0.4)

    details = {
        "semantic": SemanticComparison(
            original_text_hash=original_hash,
            kandidat_text_hash=kandidat_hash,
            original_text_length=len(original_text),
            kandidat_text_length=len(kandidat_text),
            original_text_preview=original_text[:220],
            kandidat_text_preview=kandidat_text[:220],
            original_embedding_cached=original_cached,
            kandidat_embedding_cached=kandidat_cached,
            original_evidence=orig_ev,
            kandidat_evidence=kand_ev,
        )
    }

    return SpecSimilarityResult(
        score=round(score, 4),
        confidence=round(max(0.0, min(1.0, confidence)), 3),
        evidence_trail=trail,
        common_props=common,
        missing_in_kandidat=missing_in_kandidat,
        extra_in_kandidat=extra_in_kandidat,
        details=details,
    )
