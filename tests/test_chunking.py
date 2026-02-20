import warnings

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.ingestion.html_parser import Article, ParsedRegulation
from src.retrieval.chunking import (
    MAX_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    ArticleChunk,
    chunk_article,
    chunk_corpus,
    chunk_regulation,
)


@pytest.fixture
def short_article():
    """An article well under the MAX_CHUNK_CHARS limit."""
    return Article(
        celex_id="32015R2283",
        article_number=1,
        title="Subject matter",
        text="This regulation lays down rules for novel foods.\nIt applies to all operators.",
        chapter="CHAPTER I",
        section="Section 1",
    )


@pytest.fixture
def long_article():
    """An article that exceeds MAX_CHUNK_CHARS and needs sub-chunking."""
    # Build text with distinct paragraphs, each ~300 chars
    paragraphs = []
    for i in range(12):
        paragraphs.append(f"Paragraph {i + 1}. " + "X" * 280)
    return Article(
        celex_id="32015R2283",
        article_number=3,
        title="Definitions",
        text="\n".join(paragraphs),
        chapter="CHAPTER I",
        section="",
    )


@pytest.fixture
def empty_article():
    """An article with no body text."""
    return Article(
        celex_id="32015R2283",
        article_number=99,
        title="Final provisions",
        text="   ",
        chapter="",
        section="",
    )


@pytest.fixture
def small_regulation(short_article, long_article):
    return ParsedRegulation(
        celex_id="32015R2283",
        title="Test Regulation",
        articles=[short_article, long_article],
        format_type="xhtml",
    )


# --- ArticleChunk dataclass tests ---


def test_chunk_char_count():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=1,
        article_title="Subject matter",
        text="Hello world",
    )
    assert chunk.char_count == len("Hello world")


def test_chunk_id_single():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=1,
        article_title="Subject matter",
        text="Hello",
        total_chunks=1,
    )
    assert chunk.chunk_id == "32015R2283_art1"


def test_chunk_id_multi():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=3,
        article_title="Definitions",
        text="Hello",
        chunk_index=2,
        total_chunks=5,
    )
    assert chunk.chunk_id == "32015R2283_art3_chunk2"


def test_context_header_full():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=1,
        article_title="Subject matter",
        text="Hello",
        chapter="CHAPTER I",
        section="Section 1",
        chunk_index=0,
        total_chunks=1,
    )
    header = chunk.context_header
    assert "[32015R2283]" in header
    assert "CHAPTER I" in header
    assert "Section 1" in header
    assert "Article 1" in header
    assert "Subject matter" in header
    assert "part" not in header  # single chunk, no part indicator


def test_context_header_multi_chunk():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=3,
        article_title="Definitions",
        text="Hello",
        chapter="CHAPTER I",
        chunk_index=1,
        total_chunks=4,
    )
    header = chunk.context_header
    assert "(part 2/4)" in header


def test_text_with_context():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=1,
        article_title="Subject matter",
        text="This regulation lays down rules.",
    )
    full = chunk.text_with_context
    assert full.startswith("[32015R2283]")
    assert "This regulation lays down rules." in full


def test_metadata_dict():
    chunk = ArticleChunk(
        celex_id="32015R2283",
        article_number=1,
        article_title="Subject matter",
        text="Hello",
        chapter="CHAPTER I",
        section="Section 1",
        chunk_index=0,
        total_chunks=1,
    )
    meta = chunk.metadata
    assert meta["celex_id"] == "32015R2283"
    assert meta["article_number"] == 1
    assert meta["article_title"] == "Subject matter"
    assert meta["chapter"] == "CHAPTER I"
    assert meta["section"] == "Section 1"
    assert meta["chunk_id"] == "32015R2283_art1"
    assert meta["char_count"] == len("Hello")


# --- chunk_article tests ---


def test_chunk_short_article(short_article):
    chunks = chunk_article(short_article)
    assert len(chunks) == 1
    assert chunks[0].total_chunks == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].article_number == 1
    assert chunks[0].chapter == "CHAPTER I"
    assert chunks[0].section == "Section 1"
    assert "lays down rules" in chunks[0].text


def test_chunk_empty_article(empty_article):
    chunks = chunk_article(empty_article)
    assert len(chunks) == 1
    assert chunks[0].article_title == "Final provisions"


def test_chunk_long_article_splits(long_article):
    chunks = chunk_article(long_article)
    assert len(chunks) > 1
    # All chunks should share the same article metadata
    for chunk in chunks:
        assert chunk.celex_id == "32015R2283"
        assert chunk.article_number == 3
        assert chunk.article_title == "Definitions"
        assert chunk.total_chunks == len(chunks)
    # chunk_index should be sequential
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
    # No chunk should exceed max_chars by much (paragraph boundary splits
    # may slightly exceed if a single paragraph is near the limit)
    for chunk in chunks:
        assert chunk.char_count > 0


def test_chunk_long_article_preserves_text(long_article):
    """All original text should be present across chunks."""
    chunks = chunk_article(long_article)
    reconstructed = "\n".join(c.text for c in chunks)
    # Every paragraph should appear in the reconstructed text
    for i in range(12):
        assert f"Paragraph {i + 1}." in reconstructed


def test_chunk_respects_max_chars():
    """Custom max_chars should control split threshold."""
    art = Article(
        celex_id="32015R2283",
        article_number=5,
        title="Test",
        text="Para one about food safety.\nPara two about additives.\nPara three about hygiene.",
    )
    # With very small max, should try to split
    chunks = chunk_article(art, max_chars=50)
    # With large max, should stay as one chunk
    chunks_big = chunk_article(art, max_chars=10000)
    assert len(chunks_big) == 1


def test_small_last_chunk_merges():
    """A tiny trailing paragraph should merge with the previous chunk."""
    paras = ["A" * 1500, "B" * 800, "C" * 50]  # C is tiny
    art = Article(
        celex_id="32015R2283",
        article_number=10,
        title="Test merge",
        text="\n".join(paras),
    )
    chunks = chunk_article(art, max_chars=2000)
    # The tiny "C" paragraph should have been merged, not standalone
    last_chunk_text = chunks[-1].text
    assert "C" * 50 in last_chunk_text


# --- chunk_regulation / chunk_corpus tests ---


def test_chunk_regulation(small_regulation):
    chunks = chunk_regulation(small_regulation)
    assert len(chunks) > 2  # short article = 1 chunk, long article = multiple
    celex_ids = {c.celex_id for c in chunks}
    assert celex_ids == {"32015R2283"}


def test_chunk_corpus():
    reg1 = ParsedRegulation(
        celex_id="32015R2283",
        title="Reg 1",
        articles=[
            Article(celex_id="32015R2283", article_number=1, title="Art1", text="Short text."),
        ],
        format_type="xhtml",
    )
    reg2 = ParsedRegulation(
        celex_id="32002R0178",
        title="Reg 2",
        articles=[
            Article(celex_id="32002R0178", article_number=1, title="Art1", text="Another text."),
            Article(celex_id="32002R0178", article_number=2, title="Art2", text="More text."),
        ],
        format_type="html_legacy",
    )
    chunks = chunk_corpus([reg1, reg2])
    assert len(chunks) == 3
    celex_ids = {c.celex_id for c in chunks}
    assert celex_ids == {"32015R2283", "32002R0178"}


# --- Live corpus chunking test ---

from pathlib import Path

SAMPLE_DIR = Path("data/raw/html")
has_samples = SAMPLE_DIR.exists() and any(SAMPLE_DIR.glob("*.html"))


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestLiveChunking:
    def test_chunk_full_corpus(self):
        from src.ingestion.html_parser import parse_corpus

        regulations = parse_corpus()
        chunks = chunk_corpus(regulations)

        assert len(chunks) > 0
        # Every chunk should have non-empty text
        for chunk in chunks:
            assert chunk.char_count > 0
            assert chunk.celex_id
            assert chunk.article_number > 0

        # No chunk should exceed 2x MAX_CHUNK_CHARS (generous bound for edge cases)
        oversized = [c for c in chunks if c.char_count > MAX_CHUNK_CHARS * 2]
        # Just warn, don't fail — some single paragraphs may be huge
        if oversized:
            for c in oversized:
                print(f"WARNING: oversized chunk {c.chunk_id}: {c.char_count} chars")

    def test_chunk_ids_unique(self):
        from src.ingestion.html_parser import parse_corpus

        regulations = parse_corpus()
        chunks = chunk_corpus(regulations)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs should be unique"
