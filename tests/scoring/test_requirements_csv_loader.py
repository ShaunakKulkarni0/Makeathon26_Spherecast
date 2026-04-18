from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from tests.scoring.csv_loader import load_requirements_csv


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


if __name__ == "__main__":
    unittest.main()
