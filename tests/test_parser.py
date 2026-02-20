import warnings
from pathlib import Path

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.ingestion.html_parser import (
    Article,
    ParsedRegulation,
    detect_format,
    parse_regulation,
)

SAMPLE_DIR = Path("data/raw/html")

# Only run live file tests if sample data exists
has_samples = SAMPLE_DIR.exists() and any(SAMPLE_DIR.glob("*.html"))


@pytest.fixture
def xhtml_doc():
    """Minimal XHTML document mimicking newer EUR-Lex format."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <body>
    <div class="eli-container">
        <div class="eli-main-title"><p class="oj-doc-ti">TEST REGULATION</p></div>
        <div class="eli-subdivision" id="enc_1">
            <div class="eli-subdivision" id="art_1">
                <p class="oj-ti-art">Article 1</p>
                <div>
                    <p class="oj-sti-art">Subject matter</p>
                    <p class="oj-normal">This regulation lays down rules.</p>
                    <p class="oj-normal">It applies to all food business operators.</p>
                </div>
            </div>
            <div class="eli-subdivision" id="art_2">
                <p class="oj-ti-art">Article 2</p>
                <div>
                    <p class="oj-sti-art">Definitions</p>
                    <p class="oj-normal">"food" means any substance intended for human consumption.</p>
                </div>
            </div>
        </div>
    </div>
    </body>
    </html>"""


@pytest.fixture
def legacy_html_doc():
    """Minimal HTML document mimicking older EUR-Lex format."""
    return """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html><body>
    <div id="TexteOnly">
    <p></p>
    <TXT_TE>
    <p>Test Regulation</p>
    <p>of 1 January 2002</p>
    <p>THE COUNCIL,</p>
    <p>Whereas:</p>
    <p>(1) Recital text here.</p>
    <p>Article 1</p>
    <p>Subject matter</p>
    <p>This regulation establishes general principles.</p>
    <p>It covers all food operators.</p>
    <p>Article 2</p>
    <p>Scope</p>
    <p>This regulation applies to food and feed.</p>
    <p>Article 3</p>
    <p>Definitions</p>
    <p>1. "food" means any substance.</p>
    <p>2. "feed" means any substance for animals.</p>
    </TXT_TE>
    </div>
    </body></html>"""


def test_detect_xhtml_format(xhtml_doc, tmp_path):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(xhtml_doc, "lxml")
    assert detect_format(soup) == "xhtml"


def test_detect_legacy_format(legacy_html_doc, tmp_path):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(legacy_html_doc, "lxml")
    assert detect_format(soup) == "html_legacy"


def test_parse_xhtml_articles(xhtml_doc, tmp_path):
    html_file = tmp_path / "32099R0001.html"
    html_file.write_text(xhtml_doc)

    result = parse_regulation(html_file, "32099R0001")

    assert isinstance(result, ParsedRegulation)
    assert result.celex_id == "32099R0001"
    assert result.format_type == "xhtml"
    assert len(result.articles) == 2
    assert result.articles[0].article_number == 1
    assert result.articles[0].title == "Subject matter"
    assert "lays down rules" in result.articles[0].text
    assert result.articles[1].article_number == 2
    assert result.articles[1].title == "Definitions"


def test_parse_legacy_articles(legacy_html_doc, tmp_path):
    html_file = tmp_path / "32099R0002.html"
    html_file.write_text(legacy_html_doc)

    result = parse_regulation(html_file, "32099R0002")

    assert isinstance(result, ParsedRegulation)
    assert result.celex_id == "32099R0002"
    assert result.format_type == "html_legacy"
    assert len(result.articles) == 3
    assert result.articles[0].article_number == 1
    assert result.articles[0].title == "Subject matter"
    assert "general principles" in result.articles[0].text
    assert result.articles[2].article_number == 3
    assert result.articles[2].title == "Definitions"


def test_article_dataclass():
    art = Article(
        celex_id="32015R2283",
        article_number=3,
        title="Definitions",
        text="Some text",
        chapter="CHAPTER I",
        section="Section 1",
    )
    assert art.celex_id == "32015R2283"
    assert art.article_number == 3
    assert art.chapter == "CHAPTER I"


# --- Live file tests (only run if sample data exists) ---


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestLiveFiles:
    def test_parse_novel_foods_xhtml(self):
        result = parse_regulation(SAMPLE_DIR / "32015R2283.html", "32015R2283")
        assert result.format_type == "xhtml"
        assert len(result.articles) == 36
        assert result.articles[0].article_number == 1
        assert result.articles[0].title == "Subject matter and purpose"
        assert result.articles[-1].article_number == 36

    def test_parse_general_food_law_legacy(self):
        result = parse_regulation(SAMPLE_DIR / "32002R0178.html", "32002R0178")
        assert result.format_type == "html_legacy"
        assert len(result.articles) == 65
        assert result.articles[0].article_number == 1
        assert result.articles[0].title == "Aim and scope"

    def test_parse_food_additives_xhtml(self):
        result = parse_regulation(SAMPLE_DIR / "32008R1333.html", "32008R1333")
        assert result.format_type == "xhtml"
        assert len(result.articles) == 35
        assert result.articles[0].article_number == 1

    def test_definitions_article_has_content(self):
        """Article 3 (Definitions) should have substantial text in all test docs."""
        for celex in ["32015R2283", "32002R0178", "32008R1333"]:
            path = SAMPLE_DIR / f"{celex}.html"
            if not path.exists():
                continue
            result = parse_regulation(path, celex)
            defs_articles = [a for a in result.articles if a.title.lower().startswith("definition")]
            assert len(defs_articles) > 0, f"{celex} should have a Definitions article"
            for art in defs_articles:
                assert len(art.text) > 100, (
                    f"{celex} Art {art.article_number} definitions too short: {len(art.text)} chars"
                )
