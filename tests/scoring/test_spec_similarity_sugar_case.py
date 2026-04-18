from __future__ import annotations

import unittest

from src.scoring.spec_similarity import spec_similarity
from shared.schemas import CrawledMaterial, LeadTimeInfo, MaterialProperty, PriceInfo, QualityInfo
from tests.scoring.embedding_test_utils import embedding_backend_available


def _make_material(
    material_id: str,
    name: str,
    properties: dict[str, MaterialProperty],
) -> CrawledMaterial:
    """Baut ein vollstaendiges CrawledMaterial fuer den Spec-Similarity-Test."""
    return CrawledMaterial(
        id=material_id,
        name=name,
        properties=properties,
        certifications=[],
        price=PriceInfo(value=1.0, unit="EUR/kg"),
        lead_time=LeadTimeInfo(days=7, reliability=0.9, type="standard"),
        quality=QualityInfo(),
        moq=100,
        country_of_origin="DE",
        incoterm="DDP",
    )


def _properties_to_text(material: CrawledMaterial) -> str:
    """Gibt die eingegebenen Properties als kurze Textliste zurueck."""
    if not material.properties:
        return "keine properties"
    return ", ".join(
        f"{key}={prop.value} {prop.unit}"
        for key, prop in sorted(material.properties.items())
    )


def _print_pair_result(
    original: CrawledMaterial,
    candidate: CrawledMaterial,
    score: float,
    confidence: float,
) -> None:
    """Dynamische Ausgabe basierend auf den wirklich eingegebenen Materialdaten."""
    print(f"{original.name} vs. {candidate.name}: {score:.2%} (Confidence: {confidence:.2%})")
    print(f"  Original-Daten: {_properties_to_text(original)}")
    print(f"  Kandidat-Daten: {_properties_to_text(candidate)}")


class TestSpecSimilaritySugarCase(unittest.TestCase):
    def test_sugar_case_ranks_erythrit_above_maltodextrin(self) -> None:
        """
        Gesamtziel dieses Tests:
        - Ein alltagsnahes Suessstoff-Szenario fuer Spec Similarity pruefen.
        - Erwartung: Erythrit ist semantisch naeher an Kristallzucker
          als Maltodextrin DE 18.
        """
        available, reason = embedding_backend_available()
        if not available:
            self.skipTest(reason)

        # Schritt 1: Testdaten aufbauen
        original = _make_material(
            material_id="orig_001",
            name="Kristallzucker, fein",
            properties={
                "suesskraft": MaterialProperty(value=100, unit="% referenz"),
                "kalorien": MaterialProperty(value=400, unit="kcal/100g"),
            },
        )

        kandidat1 = _make_material(
            material_id="kand_001",
            name="Erythrit",
            properties={
                "suesskraft": MaterialProperty(value=70, unit="% vs zucker"),
                "kalorien": MaterialProperty(value=20, unit="kcal/100g"),
            },
        )

        kandidat2 = _make_material(
            material_id="kand_002",
            name="Maltodextrin DE 18",
            properties={
                "suesskraft": MaterialProperty(value=5, unit="% vs zucker"),
            },
        )

        # Schritt 2: Spec Similarity berechnen
        result1 = spec_similarity(original, kandidat1)
        result2 = spec_similarity(original, kandidat2)

        # Schritt 3: Dynamische Ausgabe fuer Debug/Verstaendnis
        _print_pair_result(original, kandidat1, result1.score, result1.confidence)
        _print_pair_result(original, kandidat2, result2.score, result2.confidence)

        # Schritt 4: Kern-Assertion
        self.assertGreater(
            result1.score,
            result2.score,
            "Erwartet: Erythrit sollte hoeher als Maltodextrin scoren.",
        )


if __name__ == "__main__":
    unittest.main()
