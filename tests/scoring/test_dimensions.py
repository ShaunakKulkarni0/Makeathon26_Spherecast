from __future__ import annotations

import unittest

from shared.schemas import MaterialProperty, QualityInfo, UserRequirements
from src.scoring.compliance import compliance_score
from src.scoring.lead_time import lead_time_score
from src.scoring.price_delta import price_delta_score
from src.scoring.quality_signals import quality_signals_score
from src.scoring.spec_similarity import spec_similarity
from tests.scoring.factories import make_material


class TestScoringDimensions(unittest.TestCase):
    def test_spec_similarity_identical_materials(self) -> None:
        original = make_material("orig")
        candidate = make_material("cand")

        result = spec_similarity(original, candidate)

        self.assertAlmostEqual(result.score, 1.0, places=4)
        self.assertGreater(result.confidence, 0.0)
        self.assertEqual(result.missing_in_kandidat, [])

    def test_compliance_partial_match(self) -> None:
        original = make_material("orig", certifications=["RoHS", "ISO9001", "FDA"])
        candidate = make_material("cand", certifications=["RoHS", "REACH"])

        result = compliance_score(original, candidate)

        self.assertAlmostEqual(result.score, 1 / 3, places=4)
        self.assertEqual(result.coverage, "low")
        self.assertIn("ISO9001", result.missing)
        self.assertIn("FDA", result.missing)

    def test_price_delta_cheaper_scores_one(self) -> None:
        original = make_material("orig", price_value=2.0, incoterm="DDP")
        candidate = make_material("cand", price_value=1.8, incoterm="DDP")
        req = UserRequirements(destination_country="DE")

        result = price_delta_score(original, candidate, req)

        self.assertEqual(result.direction, "cheaper")
        self.assertAlmostEqual(result.score, 1.0, places=4)
        self.assertLess(result.delta_percent, 0)

    def test_lead_time_slower_reduces_score(self) -> None:
        original = make_material("orig", lead_days=10, lead_reliability=1.0, incoterm="DDP")
        candidate = make_material("cand", lead_days=20, lead_reliability=1.0, incoterm="DDP")

        result = lead_time_score(original, candidate, tolerance_days=1)

        self.assertEqual(result.direction, "slower")
        self.assertLess(result.score, 1.0)
        self.assertGreaterEqual(result.score, 0.0)

    def test_quality_no_data_returns_zero(self) -> None:
        no_data_quality = QualityInfo(
            supplier_rating=None,
            defect_rate=None,
            on_time_delivery=None,
            years_in_business=None,
            audit_score=None,
        )
        original = make_material("orig")
        candidate = make_material("cand", quality=no_data_quality)

        result = quality_signals_score(original, candidate)

        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("Keine Qualitätsdaten verfügbar", result.risk_factors)

    def test_spec_similarity_without_common_properties(self) -> None:
        original = make_material(
            "orig",
            properties={"a": MaterialProperty(value=1.0, unit="x")},
        )
        candidate = make_material(
            "cand",
            properties={"b": MaterialProperty(value=2.0, unit="x")},
        )

        result = spec_similarity(original, candidate)

        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.common_props, [])


if __name__ == "__main__":
    unittest.main()
