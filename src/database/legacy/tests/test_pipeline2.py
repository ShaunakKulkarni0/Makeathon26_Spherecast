"""
tests/test_pipeline2.py
Integration test for Layer 2 (Embedding & Matching Pipeline).
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

from layer2_pipeline import run_layer2_all

@pytest.fixture
def test_db_layer2():
    """Setup DB with Canonical Strings already present (Layer 1 output)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT, canonical_string TEXT);
        INSERT INTO Product (Id, SKU, Type, canonical_string) VALUES
            (1, 'RM-C1-vitamin-d3', 'raw-material', 'Cholecalciferol Vitamin D3.'),
            (2, 'RM-C37-cholecalciferol', 'raw-material', 'Cholecalciferol Vitamin D3.'),
            (3, 'RM-C6-sunflower-lecithin', 'raw-material', 'Sunflower lecithin.'),
            (4, 'FG-iherb-10421', 'finished-good', NULL);
    """)
    return conn


def mock_embeddings(inputs, model, dimensions):
    """
    Fake Embedder:
    SKU 1 & 2 get nearly identical vectors.
    SKU 3 gets a completely orthogonal (different) vector.
    """
    vectors = []
    for text in inputs:
        if "Cholecalciferol" in text:
            # Vector pointing primarily in dimension 0
            vec = [1.0, 0.1] + [0.0] * (dimensions - 2)
        else:
            # Vector pointing primarily in dimension 1
            vec = [0.0, 1.0] + [0.0] * (dimensions - 2)
        vectors.append(vec)
    return vectors


def mock_judge(model, system_prompt, user_content, **kwargs):
    """Fake Judge: Approves the Vitamin D3 match."""
    return json.dumps({
        "confidence_level": "Exact",
        "reasoning": "Both are Vitamin D3 (Cholecalciferol).",
        "compliance_flags": []
    })


@patch("embedder.create_embeddings", side_effect=mock_embeddings)
@patch("matcher.chat_completion", side_effect=mock_judge)
def test_layer2_pipeline(mock_chat, mock_embed, test_db_layer2):
    # Run Layer 2
    summary = run_layer2_all(test_db_layer2)
    
    assert summary["embedded"] == 3
    
    # 1. Check Embeddings DB
    emb_count = test_db_layer2.execute("SELECT COUNT(*) FROM sku_embeddings").fetchone()[0]
    assert emb_count == 3  # FG is ignored
    
    # 2. Check Matches DB
    matches = test_db_layer2.execute("SELECT * FROM matches").fetchall()
    
    # We should have exactly ONE match: SKU 1 <-> SKU 2
    assert len(matches) == 1
    match = matches[0]
    
    assert match["sku_id_a"] == 1
    assert match["sku_id_b"] == 2
    assert match["confidence_level"] == "Exact"
    assert match["cosine_similarity"] > 0.9  # Should be very high based on our mock vectors