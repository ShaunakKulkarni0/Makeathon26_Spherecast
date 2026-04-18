"""
tests/test_real_api.py

LIVE API TEST: This test makes ACTUAL network calls to OpenAI.
It will consume API credits and takes a few seconds to run.
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Pathing setup
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "layers"))

from layer1_pipeline import run_layer1
from layer2_pipeline import run_layer2_all

# Sicherheits-Check: Test überspringen, wenn kein API-Key gefunden wird
API_KEY = os.environ.get("OpenAIAPI")

@pytest.fixture
def live_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT)")
    skus = [
        (1, "RM-C1-vitamin-d3-cholecalciferol-67efce0f", "raw-material"),
        (2, "RM-C37-cholecalciferol-f6d103e4", "raw-material"),
        (3, "RM-C6-sunflower-lecithin-47e33a0e", "raw-material"),
        (4, "FG-iherb-10421", "finished-good")
    ]
    conn.executemany("INSERT INTO Product (Id, SKU, Type) VALUES (?, ?, ?)", skus)
    conn.commit()
    return conn

@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY is not set.")
def test_real_end_to_end_pipeline(live_db):
    print("\n\n🚀 === STARTE LIVE API TEST ===")
    
    # PHASE 1
    run_layer1(live_db)
    
    # DEBUG: Lass uns ansehen, was das LLM eigentlich geschrieben hat!
    print("\n--- WAS DAS LLM IN LAYER 1 GENERIERT HAT ---")
    rows = live_db.execute("SELECT Id, canonical_string FROM Product WHERE Type='raw-material'").fetchall()
    for row in rows:
        print(f"SKU {row['Id']}: {row['canonical_string']}")
    print("--------------------------------------------\n")

    # PHASE 2
    summary = run_layer2_all(live_db)
    
    # PHASE 3
    matches = live_db.execute("SELECT * FROM matches").fetchall()
    
    print("\n--- GEFUNDENE MATCHES ---")
    for m in matches:
        print(dict(m))
    print("-------------------------\n")
    
    assert len(matches) == 1, f"Erwartet 1 Match, aber {len(matches)} gefunden! Schau in die Logs oben."