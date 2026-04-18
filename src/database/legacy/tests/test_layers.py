"""
tests/test_layers.py

Unit tests for Layer 1 (normalizer) and Layer 2 (matcher + embedder).

All OpenAI API calls are mocked — no real network calls are made.
Run with:  pytest tests/test_layers.py -v
"""
from __future__ import annotations

import json
import math
import sqlite3
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make project root importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                  # Allows importing 'shared'
sys.path.insert(0, str(ROOT / "layers"))

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from normalizer import normalize_sku, _parse_normalization_response
from embedder   import (
    _vector_to_blob, _blob_to_vector,
    _ensure_embeddings_table, _write_embedding, load_embedding, load_all_embeddings,
    run_embedding,
)
from matcher import (
    _cosine_similarity, vector_search, _parse_judge_response, judge_pair,
)
from shared.schemas import (
    SKUCategory, ConfidenceLevel, ComplianceFlag,
    NormalizationResult, JudgeResult,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mem_db() -> sqlite3.Connection:
    """In-memory SQLite DB with a minimal Product table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE Product (
            Id               INTEGER PRIMARY KEY,
            SKU              TEXT    NOT NULL,
            CompanyId        INTEGER NOT NULL DEFAULT 1,
            Type             TEXT    NOT NULL DEFAULT 'raw-material',
            canonical_string TEXT,
            sku_category     TEXT,
            cas_number       TEXT,
            dosage_or_concentration TEXT,
            chiral_form      TEXT
        );
        INSERT INTO Product (Id, SKU, Type, canonical_string) VALUES
            (1, 'RM-C1-magnesium-citrate-aabb1122', 'raw-material',
             'Magnesium citrate (CAS 3344-18-1) is a magnesium salt of citric acid ...'),
            (2, 'RM-C2-magnesium-oxide-ccdd3344',   'raw-material',
             'Magnesium oxide (CAS 1309-48-4) is an inorganic compound ...'),
            (3, 'FG-iherb-12345',                    'finished-good', NULL);
        """
    )
    return conn


# ===========================================================================
# Layer 1 — normalizer
# ===========================================================================

class TestParseNormalizationResponse:
    VALID_PAYLOAD = {
        "category": "Chemical",
        "extracted_entities": {
            "cas_number": "3344-18-1",
            "dosage_or_concentration": "200 mg",
            "chiral_form": None,
        },
        "canonical_string": (
            "Magnesium citrate (CAS 3344-18-1, C12H10Mg3O14) is a chelated "
            "magnesium salt with high bioavailability, commonly used at 200 mg."
        ),
    }

    def test_valid_json(self):
        raw = json.dumps(self.VALID_PAYLOAD)
        result = _parse_normalization_response(raw, "Mag Cit 200mg")
        assert result.category == SKUCategory.CHEMICAL
        assert result.extracted_entities.cas_number == "3344-18-1"
        assert result.extracted_entities.dosage_or_concentration == "200 mg"
        assert "Magnesium citrate" in result.canonical_string

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps(self.VALID_PAYLOAD) + "\n```"
        result = _parse_normalization_response(raw, "test")
        assert result.category == SKUCategory.CHEMICAL

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_normalization_response("not json at all", "test")

    def test_invalid_category_raises(self):
        bad = dict(self.VALID_PAYLOAD)
        bad["category"] = "Nonexistent"
        with pytest.raises(ValueError):
            _parse_normalization_response(json.dumps(bad), "test")

    def test_missing_canonical_string_raises(self):
        bad = dict(self.VALID_PAYLOAD)
        del bad["canonical_string"]
        with pytest.raises(ValueError):
            _parse_normalization_response(json.dumps(bad), "test")

    def test_branded_category(self):
        payload = dict(self.VALID_PAYLOAD)
        payload["category"] = "Branded"
        payload["canonical_string"] = (
            "Albion TRAACS magnesium bisglycinate chelate. "
            "Substitution: never without license."
        )
        raw = json.dumps(payload)
        result = _parse_normalization_response(raw, "Albion TRAACS Mg")
        assert result.category == SKUCategory.BRANDED


class TestNormalizeSKU:
    def _mock_response(self) -> str:
        return json.dumps({
            "category": "Chemical",
            "extracted_entities": {
                "cas_number": "3344-18-1",
                "dosage_or_concentration": "200 mg",
                "chiral_form": None,
            },
            "canonical_string": "Magnesium citrate CAS 3344-18-1 200 mg tablet form.",
        })

    @patch("normalizer.chat_completion")
    def test_normalize_sku_returns_result(self, mock_chat):
        mock_chat.return_value = self._mock_response()
        result = normalize_sku("Mag Cit 200mg", sku_id=99)
        assert isinstance(result, NormalizationResult)
        assert result.sku_id == 99
        assert result.sku_name == "Mag Cit 200mg"
        assert result.category == SKUCategory.CHEMICAL

    @patch("normalizer.chat_completion")
    def test_normalize_attaches_sku_id(self, mock_chat):
        mock_chat.return_value = self._mock_response()
        result = normalize_sku("X", sku_id=42)
        assert result.sku_id == 42

    @patch("normalizer.chat_completion")
    def test_chat_called_with_correct_model(self, mock_chat):
        mock_chat.return_value = self._mock_response()
        from shared.constants import NORMALIZATION_MODEL
        normalize_sku("some sku")
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs["model"] == NORMALIZATION_MODEL
        assert call_kwargs["json_mode"] is True
        assert call_kwargs["temperature"] == 0.0


# ===========================================================================
# Layer 2 — embedder
# ===========================================================================

class TestBlobSerialization:
    def test_roundtrip_float32(self):
        original = [0.1, -0.5, 1.0, 0.0, 99.9]
        blob = _vector_to_blob(original)
        recovered = _blob_to_vector(blob)
        # float32 precision — allow small tolerance
        assert len(recovered) == len(original)
        for a, b in zip(original, recovered):
            assert abs(a - b) < 1e-5

    def test_blob_is_bytes(self):
        assert isinstance(_vector_to_blob([1.0, 2.0]), bytes)

    def test_empty_vector(self):
        assert _vector_to_blob([]) == b""
        assert _blob_to_vector(b"") == []


class TestEmbeddingsDB:
    def test_write_and_load(self, mem_db):
        _ensure_embeddings_table(mem_db)
        vector = [0.1 * i for i in range(10)]
        _write_embedding(mem_db, sku_id=1, vector=vector, model="test-model")
        mem_db.commit()
        recovered = load_embedding(mem_db, 1)
        assert recovered is not None
        assert len(recovered) == 10
        for a, b in zip(vector, recovered):
            assert abs(a - b) < 1e-5

    def test_load_nonexistent_returns_none(self, mem_db):
        _ensure_embeddings_table(mem_db)
        assert load_embedding(mem_db, 9999) is None

    def test_upsert_overwrites(self, mem_db):
        _ensure_embeddings_table(mem_db)
        _write_embedding(mem_db, 1, [0.0, 0.0], "model-v1")
        mem_db.commit()
        _write_embedding(mem_db, 1, [1.0, 1.0], "model-v2")
        mem_db.commit()
        recovered = load_embedding(mem_db, 1)
        for v in recovered:
            assert abs(v - 1.0) < 1e-5

    def test_load_all_embeddings(self, mem_db):
        _ensure_embeddings_table(mem_db)
        _write_embedding(mem_db, 1, [1.0, 0.0], "m")
        _write_embedding(mem_db, 2, [0.0, 1.0], "m")
        mem_db.commit()
        all_emb = load_all_embeddings(mem_db)
        assert len(all_emb) == 2
        ids = [e[0] for e in all_emb]
        assert 1 in ids and 2 in ids

    @patch("embedder.create_embeddings")
    def test_run_embedding_skips_finished_goods(self, mock_embed, mem_db):
        """Finished-good rows (id=3) must never be embedded."""
        _ensure_embeddings_table(mem_db)
        mock_embed.return_value = [
            [0.1] * 3072,
            [0.2] * 3072,
        ]
        n = run_embedding(mem_db, dimensions=3072)
        # Only 2 raw-material rows have canonical_strings
        assert n == 2
        all_ids = [e[0] for e in load_all_embeddings(mem_db)]
        assert 3 not in all_ids  # FG never embedded

    @patch("embedder.create_embeddings")
    def test_run_embedding_idempotent(self, mock_embed, mem_db):
        """Running twice should not re-embed already-embedded SKUs."""
        _ensure_embeddings_table(mem_db)
        mock_embed.return_value = [[0.1] * 3072, [0.2] * 3072]
        run_embedding(mem_db, dimensions=3072)
        mock_embed.reset_mock()
        mock_embed.return_value = []
        n = run_embedding(mem_db, dimensions=3072)
        assert n == 0
        mock_embed.assert_not_called()


# ===========================================================================
# Layer 2 — matcher (cosine + judge)
# ===========================================================================

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-7

    def test_orthogonal_vectors(self):
        assert abs(_cosine_similarity([1, 0], [0, 1])) < 1e-7

    def test_opposite_vectors(self):
        assert abs(_cosine_similarity([1, 0], [-1, 0]) - (-1.0)) < 1e-7

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0, 0], [1, 2]) == 0.0

    def test_dimension_mismatch_raises(self):
        with pytest.raises(ValueError, match="dimension mismatch"):
            _cosine_similarity([1, 2], [1, 2, 3])

    def test_known_value(self):
        a = [1.0, 1.0]
        b = [1.0, 0.0]
        # cos(45°) = 1/√2 ≈ 0.7071
        assert abs(_cosine_similarity(a, b) - (1 / math.sqrt(2))) < 1e-6


class TestVectorSearch:
    def _setup_embeddings(self, conn: sqlite3.Connection) -> None:
        _ensure_embeddings_table(conn)
        # sku_id=1: vector pointing along dim 0
        # sku_id=2: vector pointing along dim 1 (orthogonal to id=1)
        _write_embedding(conn, 1, [1.0, 0.0], "test")
        _write_embedding(conn, 2, [0.0, 1.0], "test")
        conn.commit()

    def test_returns_only_above_threshold(self, mem_db):
        self._setup_embeddings(mem_db)
        # Target = sku_id=1. sku_id=2 is orthogonal (sim=0) → below threshold
        candidates = vector_search(mem_db, target_sku_id=1, top_k=10, threshold=0.5)
        assert all(sim >= 0.5 for _, sim in candidates)
        assert all(sid != 1 for sid, _ in candidates)

    def test_self_excluded(self, mem_db):
        self._setup_embeddings(mem_db)
        candidates = vector_search(mem_db, 1, threshold=0.0)
        ids = [c[0] for c in candidates]
        assert 1 not in ids

    def test_top_k_respected(self, mem_db):
        _ensure_embeddings_table(mem_db)
        for i in range(1, 5):
            # All close to sku_id=1
            _write_embedding(mem_db, i, [1.0 - i * 0.01, 0.0], "test")
        mem_db.commit()
        candidates = vector_search(mem_db, 1, top_k=2, threshold=0.0)
        assert len(candidates) <= 2

    def test_missing_embedding_raises(self, mem_db):
        _ensure_embeddings_table(mem_db)
        with pytest.raises(ValueError, match="No embedding found"):
            vector_search(mem_db, target_sku_id=9999)

    def test_sorted_descending(self, mem_db):
        self._setup_embeddings(mem_db)
        # Add a third vector close to sku_id=1
        mem_db.execute(
            "INSERT INTO Product (Id, SKU, Type, canonical_string) VALUES (10, 'RM-test', 'raw-material', 'x')"
        )
        _write_embedding(mem_db, 10, [0.9, 0.1], "test")
        mem_db.commit()
        candidates = vector_search(mem_db, 1, threshold=0.0)
        sims = [c[1] for c in candidates]
        assert sims == sorted(sims, reverse=True)


class TestParseJudgeResponse:
    VALID_PAYLOAD = {
        "confidence_level": "Functional",
        "reasoning": "Same element, different salt form. Bioavailability differs.",
        "compliance_flags": ["BIOAVAILABILITY_DELTA"],
    }

    def test_valid_response(self):
        raw = json.dumps(self.VALID_PAYLOAD)
        result = _parse_judge_response(raw, sku_id_a=1, sku_id_b=2)
        assert result.confidence_level == ConfidenceLevel.FUNCTIONAL
        assert ComplianceFlag.BIOAVAILABILITY_DELTA in result.compliance_flags

    def test_empty_flags(self):
        payload = dict(self.VALID_PAYLOAD)
        payload["compliance_flags"] = []
        result = _parse_judge_response(json.dumps(payload), 1, 2)
        assert result.compliance_flags == []

    def test_all_confidence_levels(self):
        for level in ["Exact", "Functional", "Category", "No Match"]:
            payload = dict(self.VALID_PAYLOAD)
            payload["confidence_level"] = level
            result = _parse_judge_response(json.dumps(payload), 1, 2)
            assert result.confidence_level.value == level

    def test_strips_markdown_fences(self):
        raw = "```\n" + json.dumps(self.VALID_PAYLOAD) + "\n```"
        result = _parse_judge_response(raw, 1, 2)
        assert result.confidence_level == ConfidenceLevel.FUNCTIONAL

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_judge_response("not json", 1, 2)

    def test_invalid_confidence_level_raises(self):
        bad = dict(self.VALID_PAYLOAD)
        bad["confidence_level"] = "Maybe"
        with pytest.raises(ValueError):
            _parse_judge_response(json.dumps(bad), 1, 2)

    def test_invalid_flag_raises(self):
        bad = dict(self.VALID_PAYLOAD)
        bad["compliance_flags"] = ["NOT_A_REAL_FLAG"]
        with pytest.raises(ValueError):
            _parse_judge_response(json.dumps(bad), 1, 2)


class TestJudgePair:
    @patch("matcher.chat_completion")
    def test_judge_pair_attaches_metadata(self, mock_chat, mem_db):
        mock_chat.return_value = json.dumps({
            "confidence_level": "Functional",
            "reasoning": "Different salt forms of magnesium.",
            "compliance_flags": ["BIOAVAILABILITY_DELTA"],
        })
        result = judge_pair(mem_db, sku_id_a=1, sku_id_b=2, cosine_similarity=0.82)
        assert result.sku_id_a == 1
        assert result.sku_id_b == 2
        assert abs(result.cosine_similarity - 0.82) < 1e-6
        assert result.confidence_level == ConfidenceLevel.FUNCTIONAL

    @patch("matcher.chat_completion")
    def test_judge_pair_missing_canonical_raises(self, mock_chat, mem_db):
        # sku_id=3 is a finished good with no canonical_string
        with pytest.raises(ValueError, match="No canonical_string"):
            judge_pair(mem_db, sku_id_a=3, sku_id_b=1, cosine_similarity=0.9)

    @patch("matcher.chat_completion")
    def test_chat_called_with_both_canonical_strings(self, mock_chat, mem_db):
        mock_chat.return_value = json.dumps({
            "confidence_level": "Exact",
            "reasoning": "Identical.",
            "compliance_flags": [],
        })
        judge_pair(mem_db, sku_id_a=1, sku_id_b=2, cosine_similarity=0.99)
        call_kwargs = mock_chat.call_args.kwargs
        # Both canonical strings should appear in the user_content
        assert "sku_id=1" in call_kwargs["user_content"]
        assert "sku_id=2" in call_kwargs["user_content"]
        assert call_kwargs["json_mode"] is True


# ===========================================================================
# Integration smoke test (no real API calls)
# ===========================================================================

class TestLayer2IntegrationSmoke:
    @patch("matcher.chat_completion")
    @patch("embedder.create_embeddings")
    def test_full_layer2_single_sku(self, mock_embed, mock_chat, mem_db):
        """
        Smoke test: embed 2 SKUs → vector search finds candidate → judge called.
        No real API calls; all mocked.
        """
        from layer2_pipeline import run_layer2_for_sku, _ensure_matches_table

        # Step 2.1: embed
        mock_embed.return_value = [
            [1.0, 0.0, 0.0],   # sku_id=1
            [0.9, 0.1, 0.0],   # sku_id=2 — very close to sku_id=1
        ]
        _ensure_embeddings_table(mem_db)
        _write_embedding(mem_db, 1, [1.0, 0.0, 0.0], "test")
        _write_embedding(mem_db, 2, [0.9, 0.1, 0.0], "test")
        mem_db.commit()

        # Step 2.3 mock
        mock_chat.return_value = json.dumps({
            "confidence_level": "Functional",
            "reasoning": "Same element, different form.",
            "compliance_flags": [],
        })

        results = run_layer2_for_sku(
            mem_db,
            target_sku_id=1,
            threshold=0.0,
        )

        assert len(results) >= 1
        assert results[0].confidence_level == ConfidenceLevel.FUNCTIONAL

        # Verify match was written to DB
        row = mem_db.execute("SELECT * FROM matches LIMIT 1").fetchone()
        assert row is not None
        assert row["confidence_level"] == "Functional"