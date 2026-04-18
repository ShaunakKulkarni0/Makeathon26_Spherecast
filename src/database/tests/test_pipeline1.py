"""
tests/test_pipeline1.py
Integration test for Layer 1 (Normalization Pipeline).
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Pathing setup
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))            # Damit 'shared' gefunden wird
sys.path.insert(0, str(ROOT / "layers")) # Damit 'normalizer' gefunden wird

from layer1_pipeline import run_layer1


@pytest.fixture
def test_db():
    """Setup a fresh in-memory database with our 4 test SKUs."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT)")
    
    # Insert test data
    skus = [
        (1, "RM-C1-vitamin-d3-cholecalciferol-67efce0f", "raw-material"),
        (2, "RM-C37-cholecalciferol-f6d103e4", "raw-material"),
        (3, "RM-C6-sunflower-lecithin-47e33a0e", "raw-material"),
        (4, "FG-iherb-10421", "finished-good") # This MUST be ignored
    ]
    conn.executemany("INSERT INTO Product (Id, SKU, Type) VALUES (?, ?, ?)", skus)
    conn.commit()
    return conn


def mock_llm_normalization(model, system_prompt, user_content, **kwargs):
    """Fake LLM that returns a canonical string based on the input SKU."""
    if "vitamin-d3" in user_content.lower() or "cholecalciferol" in user_content.lower():
        cat = "Chemical"
        cas = "67-97-0"
        text = "Cholecalciferol (Vitamin D3). CAS 67-97-0. Fat-soluble vitamin."
    else:
        cat = "Botanical"
        cas = None
        text = "Sunflower lecithin. Plant-derived emulsifier."
        

    return json.dumps({
        "category": cat,
        "extracted_entities": {
            "cas_number": cas,
            "dosage_or_concentration": None,
            "chiral_form": None
        },
        "canonical_string": text
    })


@patch("normalizer.chat_completion", side_effect=mock_llm_normalization)
def test_layer1_pipeline(mock_chat, test_db):
    # Run the pipeline
    results = run_layer1(test_db)
    
    # 1. Pipeline should only process the 3 raw materials
    assert len(results) == 3
    assert mock_chat.call_count == 3

    # 2. Verify Database State
    rows = test_db.execute("SELECT Id, canonical_string, cas_number FROM Product ORDER BY Id").fetchall()
    
    assert rows[0]["canonical_string"] is not None  # D3 (Company 1)
    assert rows[0]["cas_number"] == "67-97-0"
    
    assert rows[1]["canonical_string"] is not None  # D3 (Company 37)
    assert rows[1]["cas_number"] == "67-97-0"
    
    assert rows[2]["canonical_string"] is not None  # Lecithin
    assert rows[2]["cas_number"] is None
    
    assert rows[3]["canonical_string"] is None      # Finished Good (Untouched)