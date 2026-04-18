"""
tests/test_full_pipeline.py
End-to-End Integration test (Layer 1 -> Layer 2 -> DB verification).
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "layers"))

from layer1_pipeline import run_layer1
from layer2_pipeline import run_layer2_all

@pytest.fixture
def raw_db():
    """Completely raw DB with just the SKUs."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT)")
    conn.executemany("INSERT INTO Product (Id, SKU, Type) VALUES (?, ?, ?)", [
        (1, "RM-C1-vitamin-d3-cholecalciferol-67efce0f", "raw-material"),
        (2, "RM-C37-cholecalciferol-f6d103e4", "raw-material"),
        (3, "RM-C6-sunflower-lecithin-47e33a0e", "raw-material"),
        (4, "FG-iherb-10421", "finished-good")
    ])
    conn.commit()
    return conn


# --- Reusing the mocks from above ---
def mock_llm_normalization(model, system_prompt, user_content, **kwargs):
    text = "Vitamin D3" if "cholecalciferol" in user_content.lower() else "Lecithin"
    return json.dumps({
        "category": "Chemical",
        "extracted_entities": {"cas_number": None, "dosage_or_concentration": None, "chiral_form": None},
        "canonical_string": text
    })

def mock_embeddings(inputs, model, dimensions):
    return [([1.0, 0.0] + [0.0]*(dimensions-2)) if "Vitamin D3" in text 
            else ([0.0, 1.0] + [0.0]*(dimensions-2)) for text in inputs]

def mock_judge(model, system_prompt, user_content, **kwargs):
    return json.dumps({
        "confidence_level": "Exact",
        "reasoning": "Match approved.",
        "compliance_flags": []
    })


@patch("normalizer.chat_completion", side_effect=mock_llm_normalization)
@patch("embedder.create_embeddings", side_effect=mock_embeddings)
@patch("matcher.chat_completion", side_effect=mock_judge)
def test_end_to_end_pipeline(mock_judge_chat, mock_embed, mock_norm_chat, raw_db):
    
    # 1. Run Data Layer
    run_layer1(raw_db)
    
    # Verify Layer 1 output exists
    assert raw_db.execute("SELECT COUNT(*) FROM Product WHERE canonical_string IS NOT NULL").fetchone()[0] == 3

    # 2. Run Comparison Layer
    run_layer2_all(raw_db)
    
    # Verify End-to-End Success!
    matches = raw_db.execute("SELECT sku_id_a, sku_id_b, confidence_level FROM matches").fetchall()
    
    assert len(matches) == 1
    assert matches[0]["sku_id_a"] == 1
    assert matches[0]["sku_id_b"] == 2
    assert matches[0]["confidence_level"] == "Exact"