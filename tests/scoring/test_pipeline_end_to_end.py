from __future__ import annotations

import unittest

from shared.schemas import (
    BOMContext,
    BOMEntry,
    ConsolidationGoals,
    ProcurementRecord,
    UserRequirements,
)
from src.scoring.pipeline import find_substitutes
from tests.scoring.embedding_test_utils import embedding_backend_available
from tests.scoring.factories import make_material


class TestPipelineEndToEnd(unittest.TestCase):
    def test_pipeline_end_to_end_without_bom_context(self) -> None:
        available, reason = embedding_backend_available()
        if not available:
            self.skipTest(reason)

        original = make_material(
            "orig",
            certifications=["RoHS", "ISO9001"],
            price_value=2.0,
            lead_days=14,
            country_of_origin="DE",
            incoterm="DDP",
        )
        strong = make_material(
            "cand-strong",
            certifications=["RoHS", "ISO9001", "REACH"],
            price_value=1.8,
            lead_days=12,
            country_of_origin="DE",
            incoterm="DDP",
        )
        medium = make_material(
            "cand-medium",
            certifications=["RoHS", "ISO9001"],
            price_value=2.05,
            lead_days=16,
            country_of_origin="DE",
            incoterm="FOB",
        )
        rejected = make_material(
            "cand-rejected",
            certifications=["RoHS"],
            price_value=4.0,
            lead_days=45,
            moq=500,
            country_of_origin="IR",
            incoterm="EXW",
        )

        req = UserRequirements(
            max_quantity=200,
            destination_country="DE",
            critical_certs=["ISO9001"],
            max_lead_time_days=30,
            max_price_multiplier=1.5,
        )

        result = find_substitutes(
            original=original,
            candidates=[strong, medium, rejected],
            user_requirements=req,
            top_n=2,
        )

        # Interface 2: Scoring -> UI contract basics
        self.assertEqual(result.original.id, "orig")
        self.assertEqual(result.metadata.total_candidates, 3)
        self.assertEqual(result.metadata.passed_knockout, 2)
        self.assertEqual(len(result.top_candidates), 2)
        self.assertEqual(len(result.rejected), 1)
        self.assertIsNone(result.consolidation)

        # Ranking and explainability payload
        first, second = result.top_candidates
        self.assertGreaterEqual(first.composite_score, second.composite_score)
        self.assertEqual(first.rank, 1)
        self.assertEqual(second.rank, 2)
        self.assertIsNotNone(first.explanation)
        self.assertIsNotNone(second.explanation)
        self.assertEqual(set(first.scores.keys()), {"spec", "compliance", "price", "lead_time", "quality"})

        # Knockout payload
        self.assertEqual(result.rejected[0].candidate.id, "cand-rejected")
        self.assertGreaterEqual(len(result.rejected[0].reasons), 1)
        self.assertGreaterEqual(len(result.rejected[0].evidence), 1)

    def test_pipeline_end_to_end_with_bom_context(self) -> None:
        available, reason = embedding_backend_available()
        if not available:
            self.skipTest(reason)

        original = make_material("orig-bom", price_value=2.0, lead_days=14, country_of_origin="DE")
        candidate = make_material(
            "cand-bom",
            price_value=1.5,
            price_tiers=[{"min_qty": 0, "price": 1.5}, {"min_qty": 1000, "price": 1.2}],
            lead_days=12,
            country_of_origin="DE",
        )

        req = UserRequirements(destination_country="DE")
        bom_context = BOMContext(
            company_boms={
                "CompanyA": [
                    BOMEntry(
                        material_id="m1",
                        material_name="PA6",
                        quantity_per_month=600.0,
                        current_supplier="SupplierX",
                        current_price=2.2,
                    )
                ],
                "CompanyB": [
                    BOMEntry(
                        material_id="m2",
                        material_name="PA6",
                        quantity_per_month=500.0,
                        current_supplier="SupplierY",
                        current_price=2.1,
                    )
                ],
            },
            historical_procurement=[
                ProcurementRecord(
                    material_id="m1",
                    supplier="SupplierX",
                    quantity=600.0,
                    price=2.2,
                    date="2026-01-10",
                )
            ],
            consolidation_goals=ConsolidationGoals(min_savings_percent=1.0),
        )

        result = find_substitutes(
            original=original,
            candidates=[candidate],
            user_requirements=req,
            top_n=1,
            bom_context=bom_context,
        )

        self.assertEqual(len(result.top_candidates), 1)
        self.assertIsNotNone(result.consolidation)
        self.assertGreaterEqual(result.consolidation.supplier_reduction, 0)
        self.assertGreaterEqual(result.consolidation.total_potential_savings, 0.0)


if __name__ == "__main__":
    unittest.main()
