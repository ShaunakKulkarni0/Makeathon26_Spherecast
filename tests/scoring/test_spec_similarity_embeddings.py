from __future__ import annotations

import unittest
import importlib

spec_module = importlib.import_module("src.scoring.spec_similarity")
from src.scoring.spec_similarity import material_to_text
from tests.scoring.embedding_test_utils import embedding_backend_available
from tests.scoring.factories import make_material


class TestSpecSimilarityEmbeddings(unittest.TestCase):
    def _require_embedding_env(self) -> None:
        available, reason = embedding_backend_available()
        if not available:
            self.skipTest(reason)

    def test_semantic_similarity_prefers_synonyms(self) -> None:
        self._require_embedding_env()
        original = make_material("orig", name="Glucose Monohydrate")
        synonym_candidate = make_material("cand-syn", name="Traubenzucker")
        unrelated_candidate = make_material("cand-unrel", name="Whey Protein Isolate")

        similar = spec_module.spec_similarity(original, synonym_candidate)
        unrelated = spec_module.spec_similarity(original, unrelated_candidate)

        self.assertGreater(similar.score, unrelated.score)
        self.assertGreaterEqual(similar.score, 0.0)
        self.assertLessEqual(similar.score, 1.0)

    def test_embedding_cache_reuses_same_text(self) -> None:
        self._require_embedding_env()
        spec_module._EMBEDDING_CACHE.clear()

        material = make_material("orig", name="Sucrose")
        text = material_to_text(material)
        key = spec_module._text_hash(text)

        first, first_cached = spec_module._get_embedding(text)
        second, second_cached = spec_module._get_embedding(text)

        self.assertFalse(first_cached)
        self.assertTrue(second_cached)
        self.assertIn(key, spec_module._EMBEDDING_CACHE)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
