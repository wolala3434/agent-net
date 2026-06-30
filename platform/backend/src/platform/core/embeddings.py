"""
Embedding utilities for Agent discovery.

Uses sentence-transformers (all-MiniLM-L6-v2) by default.
Falls back to simple keyword-based TF-IDF-like matching when the model
is unavailable (e.g. not installed, no GPU, or import fails).
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any

import numpy as np

# 国内镜像，加速 HuggingFace 模型下载（从环境变量读取，不设置默认值）
from ..config import settings
if settings.hf_endpoint:
    os.environ.setdefault("HF_ENDPOINT", settings.hf_endpoint)

# ---------------------------------------------------------------------------
# Model loading (best-effort)
# ---------------------------------------------------------------------------
_model = None
_model_available = False


def _load_model():
    """Load the sentence-transformers model. Idempotent."""
    global _model, _model_available
    if _model_available or _model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
        _model_available = True
    except Exception:
        _model_available = False


def is_model_available() -> bool:
    """Check whether the embedding model is loaded."""
    _load_model()
    return _model_available


# ---------------------------------------------------------------------------
# Embedding computation
# ---------------------------------------------------------------------------
def compute_embedding(text: str) -> np.ndarray:
    """Compute embedding vector for a text string.

    Returns a 384-dim float32 numpy array when the model is available.
    Falls back to a bag-of-words frequency vector when it is not.
    """
    _load_model()
    if _model_available:
        return _model.encode(text)
    return _fallback_embedding(text)


def compute_agent_embedding(agent_card: dict[str, Any]) -> np.ndarray:
    """Compute capability embedding from an ADL agent card.

    Concatenates all capability descriptions into a single text
    for embedding. This captures the overall capability profile.
    """
    texts = [agent_card.get("description", "")]
    for cap in agent_card.get("capabilities", []):
        texts.append(cap.get("description", ""))
        texts.append(cap.get("name", ""))
        texts.extend(cap.get("domains", []))
    combined = " ".join(t for t in texts if t)
    return compute_embedding(combined)


# ---------------------------------------------------------------------------
# Fallback: keyword frequency vector (when sentence-transformers unavailable)
# ---------------------------------------------------------------------------
_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "although",
    "this", "that", "these", "those", "it", "its", "i", "you", "he", "she",
    "they", "we", "what", "which", "who", "whom", "about", "up", "down",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize and filter stop words."""
    tokens = re.findall(r"[a-zA-Z一-鿿]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _fallback_embedding(text: str) -> np.ndarray:
    """Deterministic keyword-frequency vector as embedding fallback.

    Uses SHA-256 hashing (NOT Python's built-in ``hash()``, which is
    randomised per process via PYTHONHASHSEED).  This guarantees that
    the same text always maps to the same vector — essential for
    discovery to be reproducible.

    Dimension matches ``embedding_dim`` from config (default 384)
    so downstream cosine-similarity code works unchanged.
    """
    import hashlib

    tokens = _tokenize(text)
    if not tokens:
        return np.zeros(settings.embedding_dim, dtype=np.float32)

    vec = np.zeros(settings.embedding_dim, dtype=np.float32)
    counter = Counter(tokens)
    total = len(tokens)
    for token, count in counter.items():
        # Deterministic hash via SHA-256 (first 4 bytes → uint32)
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % settings.embedding_dim
        vec[idx] += count / total  # normalized term frequency
    return vec


# ---------------------------------------------------------------------------
# Serialisation helpers (for BLOB storage in SQLite)
# ---------------------------------------------------------------------------
def embed_to_blob(embedding: np.ndarray) -> bytes:
    """Convert numpy embedding vector to bytes for DB storage."""
    return embedding.astype(np.float32).tobytes()


def blob_to_embed(blob: bytes) -> np.ndarray:
    """Reconstruct numpy embedding vector from DB BLOB."""
    return np.frombuffer(blob, dtype=np.float32)
