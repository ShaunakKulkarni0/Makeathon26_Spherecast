from __future__ import annotations

import unittest

from shared.schemas import UserRequirements
from src.scoring.composite import calculate_composite_score
from src.scoring.pipeline import find_substitutes
from tests.scoring.factories import make_material


class TestCompositeAndPipeline(unittest.TestCase):
    def test_composite_uses_confidence_weighting(self) -> None:
        scores = {
            "spec": 1.0,
            "compliance": 0.0,
            "price": 0.0,
            "lead_time": 0.0,
            "quality": 0.0,
        }
        confidences = {
            "spec": 1.0,
            "compliance": 0.0,
            "price": 0.0,
            "lead_time": 0.0,
            "quality": 0.0,
        }

        result = calculate_composite_score(scores, confidences)

        self.assertAlmostEqual(result.score, 1.0, places=4)
        self.assertAlmostEqual(result.confidence, 0.4, places=3)

    def test_pipeline_returns_ranked_result_with_explanation(self) -> None:
        original = make_material(
            "orig",
            certifications=["RoHS", "ISO9001"],
            price_value=2.0,
            lead_days=14,
        )
        good_candidate = make_material(
            "good",
            certifications=["RoHS", "ISO9001", "REACH"],
            price_value=1.9,
            lead_days=12,
            country_of_origin="DE",
        )
        rejected_candidate = make_material(
            "reject",
            certifications=["RoHS"],
            price_value=4.5,
            lead_days=60,
            moq=1000,
            country_of_origin="IR",
        )

        req = UserRequirements(
            max_quantity=300,
            destination_country="DE",
            critical_certs=["ISO9001"],
            max_lead_time_days=30,
            max_price_multiplier=1.3,
        )

        result = find_substitutes(
            original=original,
            candidates=[good_candidate, rejected_candidate],
            user_requirements=req,
            top_n=3,
        )

        self.assertEqual(len(result.top_candidates), 1)
        self.assertEqual(result.top_candidates[0].kandidat.id, "good")
        self.assertEqual(result.top_candidates[0].rank, 1)
        self.assertIsNotNone(result.top_candidates[0].explanation)
        self.assertEqual(len(result.rejected), 1)
        self.assertEqual(result.rejected[0].candidate.id, "reject")
        self.assertEqual(result.metadata.total_candidates, 2)
        self.assertEqual(result.metadata.passed_knockout, 1)


if __name__ == "__main__":
    unittest.main()
