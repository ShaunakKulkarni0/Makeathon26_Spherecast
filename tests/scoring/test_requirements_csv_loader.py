from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from tests.scoring.csv_loader import load_requirements_csv, material_from_row


def _write_temp_csv(content: str) -> Path:
    temp = NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
    try:
        temp.write(content)
        temp.flush()
    finally:
        temp.close()
    return Path(temp.name)


class TestRequirementsCsvLoader(unittest.TestCase):
    def test_loads_with_max_quantity_header(self) -> None:
        path = _write_temp_csv(
            "max_quantity,destination_country,critical_certs_json,max_lead_time_days,max_price_multiplier\n"
            "200,DE,\"[\"\"ISO9001\"\"]\",30,1.5\n"
        )
        try:
            req = load_requirements_csv(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(req.max_quantity, 200)
        self.assertEqual(req.destination_country, "DE")
        self.assertEqual(req.critical_certs, ["ISO9001"])
        self.assertEqual(req.max_lead_time_days, 30)
        self.assertEqual(req.max_price_multiplier, 1.5)

    def test_loads_allergen_controls(self) -> None:
        path = _write_temp_csv(
            "max_quantity,destination_country,critical_certs_json,prohibited_allergens_json,allergen_policy,max_lead_time_days,max_price_multiplier\n"
            "200,DE,\"[\"\"ISO9001\"\"]\",\"[\"\"peanuts\"\",\"\"tree_nuts\"\"]\",hybrid,30,1.5\n"
        )
        try:
            req = load_requirements_csv(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(req.prohibited_allergens, ["peanuts", "tree_nuts"])
        self.assertEqual(req.allergen_policy, "hybrid")

    def test_loads_with_mqo_alias(self) -> None:
        path = _write_temp_csv(
            "destination_country,mqo,critical_certs_json,max_lead_time_days,max_price_multiplier\n"
            "DE,220,\"[\"\"ISO9001\"\"]\",25,1.4\n"
        )
        try:
            req = load_requirements_csv(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(req.max_quantity, 220)
        self.assertEqual(req.destination_country, "DE")

    def test_loads_with_max_moq_alias(self) -> None:
        path = _write_temp_csv(
            "destination_country,max_moq,critical_certs_json,max_lead_time_days,max_price_multiplier\n"
            "AT,180,\"[]\",28,1.2\n"
        )
        try:
            req = load_requirements_csv(path)
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(req.max_quantity, 180)
        self.assertEqual(req.destination_country, "AT")

    def test_raises_on_conflicting_quantity_columns(self) -> None:
        path = _write_temp_csv(
            "max_quantity,mqo,destination_country,critical_certs_json,max_lead_time_days,max_price_multiplier\n"
            "200,150,DE,\"[\"\"ISO9001\"\"]\",30,1.5\n"
        )
        try:
            with self.assertRaisesRegex(ValueError, "Konflikt in Requirements-CSV"):
                load_requirements_csv(path)
        finally:
            path.unlink(missing_ok=True)

    def test_raises_on_shifted_columns(self) -> None:
        path = _write_temp_csv(
            "destination_country,critical_certs_json,max_lead_time_days,max_price_multiplier\n"
            "DE,200,\"[\"\"ISO9001\"\"]\",30,1.5\n"
        )
        try:
            with self.assertRaisesRegex(ValueError, "mehr Werte als Header-Spalten"):
                load_requirements_csv(path)
        finally:
            path.unlink(missing_ok=True)

    def test_material_row_reads_email_and_website_variants(self) -> None:
        material = material_from_row(
            {
                "id": "cand-1",
                "name": "Candidate 1",
                "properties_json": "{\"density\": {\"value\": 1.2, \"unit\": \"g/cm3\"}}",
                "certifications_json": "[\"ISO9001\"]",
                "price_value": "2.4",
                "price_unit": "EUR/kg",
                "price_tiers_json": "[]",
                "lead_days": "14",
                "lead_reliability": "0.9",
                "lead_type": "standard",
                "supplier_rating_value": "4.2",
                "supplier_rating_reviews": "150",
                "defect_rate_value": "1.1",
                "defect_rate_sample": "1200",
                "on_time_delivery_value": "95",
                "on_time_delivery_sample": "80",
                "years_in_business": "12",
                "audit_score_value": "89",
                "audit_age_months": "8",
                "audit_passed": "true",
                "moq": "120",
                "country_of_origin": "DE",
                "incoterm": "DDP",
                "source_url": "https://supplier.example/product",
                "sales_email": "sales@supplier.example",
                "website": "https://supplier.example",
            }
        )

        self.assertEqual(material.seller_email, "sales@supplier.example")
        self.assertEqual(material.seller_website, "https://supplier.example")

    def test_material_row_falls_back_to_source_url_as_website(self) -> None:
        material = material_from_row(
            {
                "id": "cand-2",
                "name": "Candidate 2",
                "properties_json": "{\"density\": {\"value\": 1.2, \"unit\": \"g/cm3\"}}",
                "certifications_json": "[\"ISO9001\"]",
                "price_value": "2.4",
                "price_unit": "EUR/kg",
                "price_tiers_json": "[]",
                "lead_days": "14",
                "lead_reliability": "0.9",
                "lead_type": "standard",
                "supplier_rating_value": "4.2",
                "supplier_rating_reviews": "150",
                "defect_rate_value": "1.1",
                "defect_rate_sample": "1200",
                "on_time_delivery_value": "95",
                "on_time_delivery_sample": "80",
                "years_in_business": "12",
                "audit_score_value": "89",
                "audit_age_months": "8",
                "audit_passed": "true",
                "moq": "120",
                "country_of_origin": "DE",
                "incoterm": "DDP",
                "source_url": "https://supplier.example/product-2",
            }
        )

        self.assertIsNone(material.seller_email)
        self.assertEqual(material.seller_website, "https://supplier.example/product-2")


if __name__ == "__main__":
    unittest.main()
