import warnings
from pathlib import Path

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.ingestion.html_parser import (
    AnnexSection,
    Article,
    ParsedRegulation,
    _consolidated_to_base_celex,
    _parse_clg_annexes,
    _parse_xhtml_annexes,
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
def xhtml_mid_doc():
    """Minimal XHTML document mimicking mid-era EUR-Lex format (~2004-2012)."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <html><body>
    <p class="doc-ti">TEST REGULATION (mid-era)</p>
    <p class="ti-art">Article 1</p>
    <p class="sti-art">Scope</p>
    <p class="normal">This regulation applies to food hygiene.</p>
    <p class="normal">It covers all food business operators.</p>
    <p class="ti-art">Article 2</p>
    <p class="sti-art">Definitions</p>
    <p class="normal">"hygiene" means measures to ensure food safety.</p>
    </body></html>"""


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


@pytest.fixture
def clg_doc():
    """Minimal CLG consolidated HTML mimicking EUR-Lex consolidated text format."""
    return """<html><body>
    <div class="eli-container">
        <div class="eli-main-title">
            <p class="title-doc-first">REGULATION (EC) No 999/2099 OF THE COUNCIL</p>
            <p class="title-doc-first">of 1 January 2099</p>
            <p class="title-doc-last">on test food safety rules</p>
        </div>
        <div class="eli-subdivision">
            <div>
                <p class="title-division-1">CHAPTER I</p>
                <p class="title-division-2">GENERAL PROVISIONS</p>
                <div class="eli-subdivision">
                    <p class="title-article-norm">Article 1</p>
                    <div class="eli-title">
                        <p class="stitle-article-norm">Subject matter</p>
                    </div>
                    <p class="norm">This regulation lays down food safety rules.</p>
                    <div class="norm">
                        <span class="no-parag">1.</span>It applies to all food.
                    </div>
                </div>
                <div class="eli-subdivision">
                    <p class="title-article-norm">Article 2</p>
                    <div class="eli-title">
                        <p class="stitle-article-norm">Definitions</p>
                    </div>
                    <p class="norm">For the purposes of this Regulation:</p>
                    <div class="grid-container grid-list">
                        <div class="grid-list-column-1">1.</div>
                        <div class="grid-list-column-2">'food' means any substance.</div>
                    </div>
                    <div class="grid-container grid-list">
                        <div class="grid-list-column-1">2.</div>
                        <div class="grid-list-column-2">'feed' means any substance for animals.</div>
                    </div>
                </div>
            </div>
            <div>
                <p class="title-division-1">CHAPTER II</p>
                <p class="title-division-2">REQUIREMENTS</p>
                <div class="eli-subdivision">
                    <p class="title-article-norm">Article 3</p>
                    <div class="eli-title">
                        <p class="stitle-article-norm">General requirements</p>
                    </div>
                    <p class="norm">Food shall be safe for consumption.</p>
                    <p class="modref">\u25bcM1</p>
                    <p class="norm">Operators shall ensure compliance.</p>
                </div>
                <div class="eli-subdivision">
                    <p class="title-article-norm">Article 3a</p>
                    <div class="eli-title">
                        <p class="stitle-article-norm">Additional requirements</p>
                    </div>
                    <p class="norm">This article was inserted by amendment.</p>
                </div>
            </div>
        </div>
    </div>
    </body></html>"""


def test_detect_clg_format(clg_doc):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(clg_doc, "lxml")
    assert detect_format(soup) == "clg"


def test_parse_clg_articles(clg_doc, tmp_path):
    html_file = tmp_path / "02099R0999-20990101.html"
    html_file.write_text(clg_doc)

    result = parse_regulation(html_file, "02099R0999-20990101")

    assert result.format_type == "clg"
    assert result.celex_id == "02099R0999-20990101"
    assert len(result.articles) == 4

    # Article 1
    assert result.articles[0].article_number == 1
    assert result.articles[0].title == "Subject matter"
    assert "food safety rules" in result.articles[0].text
    assert result.articles[0].chapter == "CHAPTER I \u2014 GENERAL PROVISIONS"

    # Article 2 — check grid-list content is collected
    assert result.articles[1].article_number == 2
    assert result.articles[1].title == "Definitions"
    assert "'food' means" in result.articles[1].text

    # Article 3 — chapter II, modref marker skipped
    assert result.articles[2].article_number == 3
    assert result.articles[2].title == "General requirements"
    assert result.articles[2].chapter == "CHAPTER II \u2014 REQUIREMENTS"
    assert "Operators shall ensure" in result.articles[2].text
    # modref markers should not appear in text
    assert "\u25bc" not in result.articles[2].text

    # Article 3a — amendment-inserted article
    assert result.articles[3].article_number == 3
    assert result.articles[3].title == "Additional requirements"
    assert "inserted by amendment" in result.articles[3].text


def test_clg_document_title(clg_doc, tmp_path):
    html_file = tmp_path / "02099R0999-20990101.html"
    html_file.write_text(clg_doc)

    result = parse_regulation(html_file, "02099R0999-20990101")
    assert "REGULATION (EC) No 999/2099" in result.title
    assert "on test food safety rules" in result.title
    # Date line ("of 1 January 2099") should be excluded
    assert "of 1 January" not in result.title


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


def test_detect_xhtml_mid_format(xhtml_mid_doc):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(xhtml_mid_doc, "lxml")
    assert detect_format(soup) == "xhtml_mid"


def test_parse_xhtml_mid_articles(xhtml_mid_doc, tmp_path):
    html_file = tmp_path / "32099R0003.html"
    html_file.write_text(xhtml_mid_doc)

    result = parse_regulation(html_file, "32099R0003")

    assert result.format_type == "xhtml_mid"
    assert len(result.articles) == 2
    assert result.articles[0].article_number == 1
    assert result.articles[0].title == "Scope"
    assert "food hygiene" in result.articles[0].text
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

    def test_parse_food_hygiene_mid_era(self):
        path = SAMPLE_DIR / "32004R0852.html"
        if not path.exists():
            pytest.skip("32004R0852 not downloaded")
        result = parse_regulation(path, "32004R0852")
        assert result.format_type == "xhtml_mid"
        assert len(result.articles) == 18
        assert result.articles[0].article_number == 1
        assert result.articles[0].title == "Scope"

    def test_parse_all_corpus_files(self):
        """Every HTML file in the sample dir should parse without errors."""
        from src.ingestion.html_parser import parse_corpus

        regulations = parse_corpus()
        for reg in regulations:
            assert len(reg.articles) > 0, f"{reg.celex_id} has 0 articles"

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


# --- Consolidated CELEX mapping ---


class TestConsolidatedToBaseCelex:
    def test_consolidated_regulation(self):
        assert _consolidated_to_base_celex("02002R0178-20260101") == "32002R0178"

    def test_consolidated_directive(self):
        assert _consolidated_to_base_celex("02002L0046-20211012") == "32002L0046"

    def test_base_celex_unchanged(self):
        assert _consolidated_to_base_celex("32002R0178") == "32002R0178"

    def test_directive_base_unchanged(self):
        assert _consolidated_to_base_celex("32002L0046") == "32002L0046"


CLG_SAMPLE = Path("data/sample_clg.html")
has_clg_sample = CLG_SAMPLE.exists()


@pytest.mark.skipif(not has_clg_sample, reason="No CLG sample downloaded")
class TestLiveCLGFiles:
    def test_parse_general_food_law_clg(self):
        result = parse_regulation(CLG_SAMPLE, "02002R0178-20260101")
        assert result.format_type == "clg"
        assert len(result.articles) == 81  # 65 original + 16 amendment-inserted
        assert result.articles[0].article_number == 1
        assert result.articles[0].title == "Aim and scope"
        assert result.articles[-1].article_number == 65

    def test_clg_has_more_content_than_original(self):
        """Consolidated version should have more content than original."""
        orig_path = SAMPLE_DIR / "32002R0178.html"
        if not orig_path.exists():
            pytest.skip("Original file not downloaded")
        orig = parse_regulation(orig_path, "32002R0178")
        consol = parse_regulation(CLG_SAMPLE, "02002R0178-20260101")
        orig_chars = sum(len(a.text) for a in orig.articles)
        consol_chars = sum(len(a.text) for a in consol.articles)
        assert consol_chars > orig_chars, "Consolidated should have more content"
        assert len(consol.articles) > len(orig.articles), "Consolidated should have more articles"

    def test_clg_chapter_section_tracking(self):
        result = parse_regulation(CLG_SAMPLE, "02002R0178-20260101")
        # Article 1 should be in Chapter I
        art1 = result.articles[0]
        assert "CHAPTER I" in art1.chapter
        # Find first article in Chapter III (should be Art 22)
        ch3_articles = [a for a in result.articles if "CHAPTER III" in a.chapter]
        assert len(ch3_articles) > 0, "Should have Chapter III articles"
        assert ch3_articles[0].article_number == 22

    def test_clg_amendment_inserted_articles(self):
        """Amendment-inserted articles (8a, 32a, etc.) should be parsed."""
        result = parse_regulation(CLG_SAMPLE, "02002R0178-20260101")
        # Articles 8, 8a, 8b, 8c should all be present (all as article_number=8)
        art8s = [a for a in result.articles if a.article_number == 8]
        assert len(art8s) == 4, f"Expected 4 Art 8 variants, got {len(art8s)}"
        titles = {a.title for a in art8s}
        assert "Objectives of risk communication" in titles


# --- Annex parsing tests ---


@pytest.fixture
def clg_doc_with_annexes():
    """CLG document with annexes containing prose and tables."""
    return """<html><body>
    <div class="eli-container">
        <div class="eli-main-title">
            <p class="title-doc-first">REGULATION (EC) No 888/2099</p>
            <p class="title-doc-last">on test annex parsing</p>
        </div>
        <div class="eli-subdivision">
            <div class="eli-subdivision">
                <p class="title-article-norm">Article 1</p>
                <div class="eli-title">
                    <p class="stitle-article-norm">Subject matter</p>
                </div>
                <p class="norm">This regulation has annexes.</p>
            </div>
        </div>
        <hr class="separator-annex"/>
        <p class="title-annex-1">ANNEX I</p>
        <p class="title-annex-2">Conditions of use</p>
        <p class="norm">Novel foods must meet these conditions.</p>
        <p class="norm">All operators shall comply with requirements.</p>
        <table border="1"><tr><td>E100</td><td>Curcumin</td></tr></table>
        <p class="norm">Additional prose after table.</p>
        <p class="title-gr-seq-level-1">PART A</p>
        <p class="norm">Part A contains specific rules.</p>
        <div class="grid-container grid-list">
            <div class="grid-list-column-1">1.</div>
            <div class="grid-list-column-2">First condition of Part A.</div>
        </div>
        <p class="title-annex-1">ANNEX II</p>
        <p class="title-annex-2">Restricted substances</p>
        <p class="norm">These substances are restricted in novel foods.</p>
    </div>
    </body></html>"""


@pytest.fixture
def xhtml_doc_with_annexes():
    """XHTML document with annexes containing prose and tables."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <body>
    <div class="eli-container">
        <div class="eli-main-title"><p class="oj-doc-ti">TEST REGULATION</p></div>
        <div class="eli-subdivision" id="art_1">
            <p class="oj-ti-art">Article 1</p>
            <div>
                <p class="oj-sti-art">Scope</p>
                <p class="oj-normal">This regulation applies.</p>
            </div>
        </div>
    </div>
    <div class="eli-container" id="anx_I">
        <p class="oj-doc-ti">ANNEX I</p>
        <p class="oj-doc-ti">List of authorised substances</p>
        <p class="oj-normal">The following substances are authorised.</p>
        <p class="oj-normal">All conditions must be met.</p>
        <table class="oj-table"><tr><td>Data</td></tr></table>
        <p class="oj-normal">Additional requirements apply.</p>
    </div>
    <div class="eli-container" id="anx_II">
        <p class="oj-doc-ti">ANNEX II</p>
        <p class="oj-normal">Second annex prose text.</p>
    </div>
    </body>
    </html>"""


class TestCLGAnnexParsing:
    def test_clg_annexes_detected(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        assert len(annexes) >= 2  # At least ANNEX I (possibly split by part) + ANNEX II

    def test_clg_annex_number(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        annex_numbers = {a.annex_number for a in annexes}
        assert "I" in annex_numbers
        assert "II" in annex_numbers

    def test_clg_annex_prose_extracted(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        all_text = "\n".join(a.text for a in annexes)
        assert "Novel foods must meet these conditions" in all_text
        assert "operators shall comply" in all_text

    def test_clg_annex_tables_skipped(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        all_text = "\n".join(a.text for a in annexes)
        # Table content (E100, Curcumin) should not appear in prose
        assert "E100" not in all_text
        assert "Curcumin" not in all_text

    def test_clg_annex_parts_split(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        annex_i_sections = [a for a in annexes if a.annex_number == "I"]
        # Should have at least 2 sections: before PART A and PART A itself
        assert len(annex_i_sections) >= 2
        parts = [a.part for a in annex_i_sections]
        assert "PART A" in parts

    def test_clg_annex_grid_list_collected(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        all_text = "\n".join(a.text for a in annexes)
        assert "First condition of Part A" in all_text

    def test_clg_annex_celex_id(self, clg_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(clg_doc_with_annexes, "lxml")
        annexes = _parse_clg_annexes(soup, "32099R0888")
        for annex in annexes:
            assert annex.celex_id == "32099R0888"


class TestXHTMLAnnexParsing:
    def test_xhtml_annexes_detected(self, xhtml_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xhtml_doc_with_annexes, "lxml")
        annexes = _parse_xhtml_annexes(soup, "32099R0777")
        assert len(annexes) == 2

    def test_xhtml_annex_number(self, xhtml_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xhtml_doc_with_annexes, "lxml")
        annexes = _parse_xhtml_annexes(soup, "32099R0777")
        assert annexes[0].annex_number == "I"
        assert annexes[1].annex_number == "II"

    def test_xhtml_annex_prose_extracted(self, xhtml_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xhtml_doc_with_annexes, "lxml")
        annexes = _parse_xhtml_annexes(soup, "32099R0777")
        assert "following substances are authorised" in annexes[0].text
        assert "All conditions must be met" in annexes[0].text
        assert "Additional requirements apply" in annexes[0].text

    def test_xhtml_annex_tables_skipped(self, xhtml_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xhtml_doc_with_annexes, "lxml")
        annexes = _parse_xhtml_annexes(soup, "32099R0777")
        # Table content shouldn't be in prose
        all_text = "\n".join(a.text for a in annexes)
        assert "Data" not in all_text

    def test_xhtml_annex_subtitle(self, xhtml_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xhtml_doc_with_annexes, "lxml")
        annexes = _parse_xhtml_annexes(soup, "32099R0777")
        assert annexes[0].annex_title == "List of authorised substances"

    def test_xhtml_annex_celex_id(self, xhtml_doc_with_annexes):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(xhtml_doc_with_annexes, "lxml")
        annexes = _parse_xhtml_annexes(soup, "32099R0777")
        for annex in annexes:
            assert annex.celex_id == "32099R0777"


class TestAnnexIntegration:
    def test_parse_clg_includes_annexes(self, clg_doc_with_annexes, tmp_path):
        html_file = tmp_path / "02099R0888-20990101.html"
        html_file.write_text(clg_doc_with_annexes)
        result = parse_regulation(html_file, "02099R0888-20990101")
        assert len(result.articles) >= 1
        assert len(result.annexes) >= 2

    def test_parse_xhtml_includes_annexes(self, xhtml_doc_with_annexes, tmp_path):
        html_file = tmp_path / "32099R0777.html"
        html_file.write_text(xhtml_doc_with_annexes)
        result = parse_regulation(html_file, "32099R0777")
        assert len(result.articles) >= 1
        assert len(result.annexes) == 2

    def test_no_annexes_returns_empty_list(self, clg_doc, tmp_path):
        """A document without annexes should have an empty annexes list."""
        html_file = tmp_path / "02099R0999-20990101.html"
        html_file.write_text(clg_doc)
        result = parse_regulation(html_file, "02099R0999-20990101")
        assert result.annexes == []

    def test_annex_section_dataclass(self):
        section = AnnexSection(
            celex_id="32015R2283",
            annex_number="I",
            annex_title="Conditions of use",
            text="Some prose content.",
            part="PART A",
        )
        assert section.celex_id == "32015R2283"
        assert section.annex_number == "I"
        assert section.part == "PART A"


class TestParseCorpusFallback:
    """Test that parse_corpus falls back from unparseable consolidated to original."""

    def test_fallback_from_unparseable_consolidated(self, tmp_path):
        """When consolidated file can't be parsed, should fall back to original."""
        from src.ingestion.html_parser import parse_corpus

        # Write an unparseable consolidated file (stub with no articles)
        (tmp_path / "02002R0178-20260101.html").write_text(
            "<html><body><p>stub</p></body></html>"
        )
        # Write a parseable original file (xhtml format)
        (tmp_path / "32002R0178.html").write_text("""<?xml version="1.0" encoding="UTF-8"?>
        <html xmlns="http://www.w3.org/1999/xhtml"><body>
        <div class="eli-container">
            <div class="eli-main-title"><p class="oj-doc-ti">TEST REG</p></div>
            <div class="eli-subdivision" id="art_1">
                <p class="oj-ti-art">Article 1</p>
                <p class="oj-normal">Test text.</p>
            </div>
        </div></body></html>""")

        results = parse_corpus(html_dir=tmp_path)
        assert len(results) == 1
        assert results[0].celex_id == "32002R0178"
        assert len(results[0].articles) == 1

    def test_skips_when_no_parseable_file(self, tmp_path):
        """When no file can be parsed, regulation is skipped."""
        from src.ingestion.html_parser import parse_corpus

        (tmp_path / "32999R9999.html").write_text(
            "<html><body><p>no articles here</p></body></html>"
        )
        results = parse_corpus(html_dir=tmp_path)
        assert len(results) == 0
