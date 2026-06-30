"""
Unit tests for the embedding module.

Critical invariants (post-fix):
  1. Fallback embedding is **deterministic** — same text → same vector
     (the old ``hash()``-based implementation was randomised by PYTHONHASHSEED)
  2. Different texts produce different vectors (no collisions in practice)
  3. Zero-vector returned for empty input
  4. Blob serialisation round-trips correctly
"""

from __future__ import annotations

import numpy as np

from src.platform.core.embeddings import (
    _fallback_embedding,
    _tokenize,
    blob_to_embed,
    compute_agent_embedding,
    compute_embedding,
    embed_to_blob,
    is_model_available,
)
from src.platform.config import settings


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_tokenizes_english(self):
        tokens = _tokenize("The quick brown fox jumps over the lazy dog")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        # Stop words must be removed
        assert "the" not in tokens

    def test_tokenizes_chinese(self):
        tokens = _tokenize("供应链风险分析专家")
        assert len(tokens) > 0, "Chinese tokens should be extracted"

    def test_removes_short_tokens(self):
        tokens = _tokenize("a b c ab cd ef g hi")
        # "a", "b", "c", "g" are single-char; "ab", "cd", "ef", "hi" are 2-char
        assert all(len(t) > 1 for t in tokens)

    def test_empty_string(self):
        assert _tokenize("") == []


# ---------------------------------------------------------------------------
# Fallback embedding (deterministic)
# ---------------------------------------------------------------------------

class TestFallbackEmbedding:
    """The fallback must be reproducible — the whole discovery pipeline depends on it."""

    def test_deterministic_same_text(self):
        v1 = _fallback_embedding("评估特斯拉供应链风险")
        v2 = _fallback_embedding("评估特斯拉供应链风险")
        assert np.array_equal(v1, v2), (
            "Same text must produce identical vectors. "
            "The old hash()-based implementation was non-deterministic across processes."
        )

    def test_deterministic_across_calls(self):
        """Multiple calls with the same text produce byte-identical vectors."""
        text = "分析锂矿价格走势与新能源汽车行业影响"
        vectors = [_fallback_embedding(text) for _ in range(10)]
        for v in vectors[1:]:
            assert np.array_equal(vectors[0], v)

    def test_different_texts_different_vectors(self):
        v1 = _fallback_embedding("风险评估")
        v2 = _fallback_embedding("代码审查")
        assert not np.array_equal(v1, v2), (
            "Different texts should produce different vectors"
        )

    def test_correct_dimension(self):
        vec = _fallback_embedding("test text for dimension check")
        assert vec.shape == (settings.embedding_dim,)
        assert vec.dtype == np.float32

    def test_empty_text_returns_zeros(self):
        vec = _fallback_embedding("")
        assert np.allclose(vec, 0.0), "Empty text should return zero vector"

    def test_stop_words_only_returns_zeros(self):
        vec = _fallback_embedding("the a an is are was were")
        assert np.allclose(vec, 0.0), "Stop-word-only text should return zero vector"

    def test_values_are_normalized(self):
        """Token frequencies are divided by total count → values in [0, 1]."""
        vec = _fallback_embedding("supply chain risk analysis for electric vehicle battery")
        assert np.all(vec >= 0.0)
        assert np.all(vec <= 1.0)


# ---------------------------------------------------------------------------
# Embedding blobs
# ---------------------------------------------------------------------------

class TestBlobSerialization:
    """Embedding vectors must survive a bytes round-trip."""

    def test_round_trip(self):
        original = np.random.randn(settings.embedding_dim).astype(np.float32)
        blob = embed_to_blob(original)
        restored = blob_to_embed(blob)
        assert np.allclose(original, restored, atol=1e-6)

    def test_empty_blob(self):
        original = np.zeros(settings.embedding_dim, dtype=np.float32)
        blob = embed_to_blob(original)
        restored = blob_to_embed(blob)
        assert np.allclose(original, restored)

    def test_blob_size_matches_dimension(self):
        """Each float32 is 4 bytes."""
        original = np.zeros(settings.embedding_dim, dtype=np.float32)
        blob = embed_to_blob(original)
        assert len(blob) == settings.embedding_dim * 4


# ---------------------------------------------------------------------------
# Agent embedding
# ---------------------------------------------------------------------------

class TestComputeAgentEmbedding:
    """Agent embedding must aggregate all capability descriptions."""

    def test_empty_card(self):
        card = {"description": "", "capabilities": []}
        vec = compute_agent_embedding(card)
        assert vec.shape == (settings.embedding_dim,)

    def test_aggregates_domains_and_descriptions(self):
        card = {
            "description": "风险评估专家",
            "capabilities": [
                {
                    "id": "risk-1",
                    "name": "财务风险分析",
                    "description": "分析财务报表中的风险因素",
                    "domains": ["analysis.financial", "analysis.risk"],
                }
            ],
        }
        vec = compute_agent_embedding(card)
        assert vec.shape == (settings.embedding_dim,)
        # With description + capability info, should be non-zero
        assert not np.allclose(vec, 0.0)


# ---------------------------------------------------------------------------
# Model availability
# ---------------------------------------------------------------------------

class TestModelAvailability:
    """is_model_available() must not crash, regardless of environment."""

    def test_does_not_throw(self):
        """This test passes whether or not sentence-transformers is installed."""
        result = is_model_available()
        assert isinstance(result, bool)

    def test_compute_embedding_always_returns_vector(self):
        """compute_embedding must always return a valid vector, even without the model."""
        vec = compute_embedding("any text at all")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (settings.embedding_dim,)
        assert vec.dtype == np.float32
