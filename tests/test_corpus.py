from src.ingestion.corpus import CATEGORIES, CORPUS


def test_corpus_not_empty():
    assert len(CORPUS) > 0


def test_every_entry_has_required_fields():
    for celex_id, entry in CORPUS.items():
        assert "category" in entry, f"{celex_id} missing 'category'"
        assert "title" in entry, f"{celex_id} missing 'title'"
        assert "description" in entry, f"{celex_id} missing 'description'"


def test_all_categories_are_defined():
    corpus_categories = {entry["category"] for entry in CORPUS.values()}
    for cat in corpus_categories:
        assert cat in CATEGORIES, f"Category '{cat}' used in CORPUS but not defined in CATEGORIES"


def test_celex_id_format():
    """CELEX IDs should match the pattern: 3YYYYLNNNN (3 = sector, L = type, NNNN = number)."""
    for celex_id in CORPUS:
        assert celex_id[0] == "3", f"{celex_id} doesn't start with sector '3'"
        assert len(celex_id) >= 10, f"{celex_id} is too short for a valid CELEX ID"
        # Year part (positions 1-4) should be numeric
        assert celex_id[1:5].isdigit(), f"{celex_id} has non-numeric year"


def test_no_duplicate_titles():
    titles = [entry["title"] for entry in CORPUS.values()]
    assert len(titles) == len(set(titles)), "Duplicate titles found in CORPUS"
