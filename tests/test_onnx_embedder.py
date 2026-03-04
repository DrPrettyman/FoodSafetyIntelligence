"""Tests for the ONNX Runtime embedder."""

import numpy as np
import pytest

from src.indexing.onnx_embedder import OnnxEmbedder


@pytest.fixture(scope="module")
def embedder():
    return OnnxEmbedder()


def test_single_text(embedder):
    """Single text produces a 384-dim unit-norm vector."""
    emb = embedder.encode(["food safety regulation"])
    assert emb.shape == (1, 384)
    assert abs(np.linalg.norm(emb[0]) - 1.0) < 1e-5


def test_batch_texts(embedder):
    """Batch encoding produces correct shape."""
    texts = ["novel food", "food additive", "labelling requirements", "insect protein"]
    emb = embedder.encode(texts)
    assert emb.shape == (4, 384)
    for i in range(4):
        assert abs(np.linalg.norm(emb[i]) - 1.0) < 1e-5


def test_no_normalize(embedder):
    """Without normalization, norms are not 1."""
    emb = embedder.encode(["food safety"], normalize_embeddings=False)
    norm = np.linalg.norm(emb[0])
    assert norm != pytest.approx(1.0, abs=0.01)


def test_batch_size_chunking(embedder):
    """Results identical regardless of batch_size."""
    texts = [f"regulatory text {i}" for i in range(10)]
    emb_bs1 = embedder.encode(texts, batch_size=1)
    emb_bs4 = embedder.encode(texts, batch_size=4)
    emb_bs10 = embedder.encode(texts, batch_size=10)
    np.testing.assert_allclose(emb_bs1, emb_bs4, atol=1e-5)
    np.testing.assert_allclose(emb_bs1, emb_bs10, atol=1e-5)


def test_semantic_ordering(embedder):
    """Novel food query is more similar to novel food text than to labelling text."""
    query = embedder.encode(["novel food definition"])
    novel_food = embedder.encode(["novel food was not used for human consumption before 1997"])
    labelling = embedder.encode(["mandatory labelling of food business operator address"])

    score_relevant = float((query @ novel_food.T).item())
    score_irrelevant = float((query @ labelling.T).item())
    assert score_relevant > score_irrelevant
