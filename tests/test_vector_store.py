import tempfile
import warnings
from pathlib import Path

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from src.ingestion.html_parser import Article
from src.indexing.vector_store import VectorStore
from src.retrieval.chunking import ArticleChunk, chunk_article


@pytest.fixture
def sample_chunks():
    """A small set of chunks for testing."""
    articles = [
        Article(
            celex_id="32015R2283",
            article_number=1,
            title="Subject matter",
            text="This Regulation lays down rules for the placing on the market "
            "of novel foods within the Union.",
        ),
        Article(
            celex_id="32015R2283",
            article_number=3,
            title="Definitions",
            text="'novel food' means any food that was not used for human consumption "
            "to a significant degree within the Union before 15 May 1997.",
        ),
        Article(
            celex_id="32008R1333",
            article_number=1,
            title="Subject matter",
            text="This Regulation lays down rules on food additives used in foods.",
        ),
        Article(
            celex_id="32008R1333",
            article_number=3,
            title="Definitions",
            text="'food additive' shall mean any substance not normally consumed "
            "as a food in itself and not normally used as a characteristic "
            "ingredient of food.",
        ),
        Article(
            celex_id="32011R1169",
            article_number=9,
            title="List of mandatory particulars",
            text="The following particulars shall be mandatory: the name of the food, "
            "the list of ingredients, any ingredient causing allergies, "
            "the quantity of certain ingredients, the net quantity, "
            "the date of minimum durability, storage conditions, "
            "the name and address of the food business operator.",
        ),
    ]
    chunks = []
    for art in articles:
        chunks.extend(chunk_article(art))
    return chunks


@pytest.fixture
def temp_store(sample_chunks):
    """A temporary vector store with sample chunks indexed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vs = VectorStore(persist_dir=tmpdir)
        vs.index_chunks(sample_chunks)
        yield vs


def test_index_chunks(sample_chunks):
    with tempfile.TemporaryDirectory() as tmpdir:
        vs = VectorStore(persist_dir=tmpdir)
        assert vs.count == 0
        indexed = vs.index_chunks(sample_chunks)
        assert indexed == len(sample_chunks)
        assert vs.count == len(sample_chunks)


def test_search_returns_results(temp_store):
    results = temp_store.search("novel food definition", n_results=3)
    assert len(results) > 0
    assert len(results) <= 3


def test_search_result_format(temp_store):
    results = temp_store.search("food additive", n_results=1)
    assert len(results) == 1
    r = results[0]
    assert "chunk_id" in r
    assert "text" in r
    assert "metadata" in r
    assert "score" in r
    assert isinstance(r["score"], float)


def test_search_filtered_by_celex(temp_store):
    results = temp_store.search(
        "definitions",
        celex_ids=["32015R2283"],
        n_results=10,
    )
    for r in results:
        assert r["metadata"]["celex_id"] == "32015R2283"


def test_search_filtered_multiple_celex(temp_store):
    results = temp_store.search(
        "definitions",
        celex_ids=["32015R2283", "32008R1333"],
        n_results=10,
    )
    for r in results:
        assert r["metadata"]["celex_id"] in {"32015R2283", "32008R1333"}


def test_search_filtered_empty_celex(temp_store):
    results = temp_store.search(
        "definitions",
        celex_ids=["32099R9999"],  # non-existent
        n_results=10,
    )
    assert results == []


def test_search_semantic_relevance(temp_store):
    """Novel food query should rank novel food chunks higher than labelling."""
    results = temp_store.search("novel food ingredients", n_results=5)
    # First result should be from the novel food regulation
    top_celex = results[0]["metadata"]["celex_id"]
    assert top_celex == "32015R2283"


def test_persistence(sample_chunks):
    """Store should persist and reload from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Index
        vs1 = VectorStore(persist_dir=tmpdir)
        vs1.index_chunks(sample_chunks)
        assert vs1.count == len(sample_chunks)

        # Reload
        vs2 = VectorStore(persist_dir=tmpdir)
        assert vs2.count == len(sample_chunks)

        # Search still works
        results = vs2.search("novel food", n_results=3)
        assert len(results) > 0


def test_delete_all(sample_chunks):
    with tempfile.TemporaryDirectory() as tmpdir:
        vs = VectorStore(persist_dir=tmpdir)
        vs.index_chunks(sample_chunks)
        assert vs.count > 0
        vs.delete_all()
        assert vs.count == 0


def test_empty_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        vs = VectorStore(persist_dir=tmpdir)
        results = vs.search("anything")
        assert results == []
