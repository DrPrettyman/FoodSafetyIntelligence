import warnings
from pathlib import Path

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.extraction.entity_extractor import (
    CrossReference,
    DefinedTerm,
    EntityIndex,
    extract_cross_references,
    extract_defined_terms,
    extract_entities,
)
from src.ingestion.html_parser import Article, ParsedRegulation


# --- Fixtures ---


@pytest.fixture
def definitions_article_single_quotes():
    """Article using single-quote convention: 'term' means ..."""
    return Article(
        celex_id="32008R1333",
        article_number=3,
        title="Definitions",
        text=(
            "For the purposes of this Regulation the following definitions shall also apply:\n"
            "(a)\n"
            "'food additive' shall mean any substance not normally consumed as a food;\n"
            "(b)\n"
            "'processing aid' shall mean any substance which is not consumed as a food;\n"
            "(c)\n"
            "'quantum satis' shall mean that no maximum numerical level is specified."
        ),
        chapter="CHAPTER I",
    )


@pytest.fixture
def definitions_article_double_quotes():
    """Article using double-quote convention: "term" means ..."""
    return Article(
        celex_id="32004R0852",
        article_number=2,
        title="Definitions",
        text=(
            '1.   For the purposes of this Regulation:\n'
            '(a)\u201c food hygiene \u201d means the measures and conditions necessary;\n'
            '(b)\u201c primary products \u201d means products of primary production;\n'
            '(c)\u201c establishment \u201d means any unit of a food business.'
        ),
    )


@pytest.fixture
def definitions_article_parenthetical():
    """Article with parenthetical alias: "food" (or "foodstuff") means ..."""
    return Article(
        celex_id="32002R0178",
        article_number=2,
        title='Definition of "food"',
        text=(
            'For the purposes of this Regulation, "food" (or "foodstuff") means '
            "any substance or product intended to be ingested by humans."
        ),
    )


@pytest.fixture
def article_with_cross_refs():
    """Article referencing other regulations."""
    return Article(
        celex_id="32015R2283",
        article_number=3,
        title="Definitions",
        text=(
            "The definitions laid down in Regulation (EC) No 178/2002 apply.\n"
            "The definition in Directive 2001/18/EC also applies.\n"
            "See also Commission Regulation (EU) No 1169/2011."
        ),
    )


@pytest.fixture
def empty_article():
    return Article(
        celex_id="32015R2283",
        article_number=99,
        title="Final provisions",
        text="",
    )


# --- extract_defined_terms tests ---


def test_extract_single_quote_terms(definitions_article_single_quotes):
    terms = extract_defined_terms(definitions_article_single_quotes)
    term_names = [t.term.lower() for t in terms]
    assert "food additive" in term_names
    assert "processing aid" in term_names
    assert "quantum satis" in term_names
    assert len(terms) == 3


def test_extract_double_quote_terms(definitions_article_double_quotes):
    terms = extract_defined_terms(definitions_article_double_quotes)
    term_names = [t.term.lower().strip() for t in terms]
    assert "food hygiene" in term_names
    assert "primary products" in term_names
    assert "establishment" in term_names


def test_extract_parenthetical_alias(definitions_article_parenthetical):
    terms = extract_defined_terms(definitions_article_parenthetical)
    term_names = [t.term.lower() for t in terms]
    assert "food" in term_names


def test_extract_empty_article(empty_article):
    terms = extract_defined_terms(empty_article)
    assert terms == []


def test_term_metadata(definitions_article_single_quotes):
    terms = extract_defined_terms(definitions_article_single_quotes)
    fa = [t for t in terms if t.term.lower() == "food additive"][0]
    assert fa.celex_id == "32008R1333"
    assert fa.article_number == 3
    assert fa.definition_snippet  # should have some text
    assert fa.category == "food_additives"


def test_no_duplicate_terms():
    """Same term quoted twice in one article should only appear once."""
    art = Article(
        celex_id="32099R0001",
        article_number=1,
        title="Definitions",
        text="'food' means substance. Also, 'food' means edible matter.",
    )
    terms = extract_defined_terms(art)
    food_terms = [t for t in terms if t.term.lower() == "food"]
    assert len(food_terms) == 1


# --- extract_cross_references tests ---


def test_extract_cross_references(article_with_cross_refs):
    refs = extract_cross_references(article_with_cross_refs)
    ref_nums = [r.target_regulation_number for r in refs]
    assert "178/2002" in ref_nums
    assert "1169/2011" in ref_nums


def test_cross_ref_metadata(article_with_cross_refs):
    refs = extract_cross_references(article_with_cross_refs)
    ref_178 = [r for r in refs if r.target_regulation_number == "178/2002"][0]
    assert ref_178.source_celex == "32015R2283"
    assert ref_178.source_article == 3
    assert ref_178.context  # should have surrounding text


def test_cross_ref_empty_article(empty_article):
    refs = extract_cross_references(empty_article)
    assert refs == []


def test_no_duplicate_cross_refs():
    """Same regulation referenced twice in one article should appear once."""
    art = Article(
        celex_id="32099R0001",
        article_number=1,
        title="Scope",
        text="See Regulation (EC) No 178/2002. Also see Regulation (EC) No 178/2002 again.",
    )
    refs = extract_cross_references(art)
    refs_178 = [r for r in refs if r.target_regulation_number == "178/2002"]
    assert len(refs_178) == 1


# --- EntityIndex tests ---


def test_entity_index_term_to_sources():
    idx = EntityIndex(
        defined_terms=[
            DefinedTerm(term="food", celex_id="32002R0178", article_number=2, definition_snippet="..."),
            DefinedTerm(term="food", celex_id="32017R0625", article_number=3, definition_snippet="..."),
            DefinedTerm(term="feed", celex_id="32002R0178", article_number=3, definition_snippet="..."),
        ]
    )
    t2s = idx.term_to_sources
    assert len(t2s["food"]) == 2
    assert len(t2s["feed"]) == 1


def test_entity_index_celex_to_terms():
    idx = EntityIndex(
        defined_terms=[
            DefinedTerm(term="food", celex_id="32002R0178", article_number=2, definition_snippet="..."),
            DefinedTerm(term="feed", celex_id="32002R0178", article_number=3, definition_snippet="..."),
            DefinedTerm(term="additive", celex_id="32008R1333", article_number=3, definition_snippet="..."),
        ]
    )
    c2t = idx.celex_to_terms
    assert len(c2t["32002R0178"]) == 2
    assert len(c2t["32008R1333"]) == 1


def test_entity_index_unique_terms():
    idx = EntityIndex(
        defined_terms=[
            DefinedTerm(term="Food", celex_id="32002R0178", article_number=2, definition_snippet="..."),
            DefinedTerm(term="food", celex_id="32017R0625", article_number=3, definition_snippet="..."),
            DefinedTerm(term="feed", celex_id="32002R0178", article_number=3, definition_snippet="..."),
        ]
    )
    assert idx.unique_terms == ["feed", "food"]


# --- Live corpus tests ---

SAMPLE_DIR = Path("data/raw/html")
has_samples = SAMPLE_DIR.exists() and any(SAMPLE_DIR.glob("*.html"))


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestLiveExtraction:
    def test_extract_from_full_corpus(self):
        from src.ingestion.html_parser import parse_corpus

        regulations = parse_corpus()
        index = extract_entities(regulations)

        # Should extract a substantial number of terms
        assert len(index.defined_terms) > 200
        assert len(index.unique_terms) > 150

        # Key terms should be found
        term_set = set(index.unique_terms)
        for expected in ["food", "feed", "food additive", "novel food", "traceability"]:
            assert expected in term_set, f"Expected term '{expected}' not found"

    def test_general_food_law_has_core_terms(self):
        from src.ingestion.html_parser import parse_corpus

        regulations = parse_corpus()
        index = extract_entities(regulations)

        gfl_terms = index.celex_to_terms.get("32002R0178", [])
        gfl_term_names = {t.term_lower for t in gfl_terms}
        for expected in ["food", "risk", "hazard", "traceability"]:
            assert expected in gfl_term_names, f"32002R0178 should define '{expected}'"

    def test_cross_references_found(self):
        from src.ingestion.html_parser import parse_corpus

        regulations = parse_corpus()
        index = extract_entities(regulations)

        assert len(index.cross_references) > 100
        # 178/2002 (General Food Law) should be referenced by many regulations
        refs_to_178 = [r for r in index.cross_references if r.target_regulation_number == "178/2002"]
        assert len(refs_to_178) > 10, "General Food Law should be widely referenced"
