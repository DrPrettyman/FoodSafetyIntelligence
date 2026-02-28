"""
Unit tests for SPARQL-based corpus discovery.

Tests use synthetic data — no network calls, no filesystem dependencies.
"""

import pytest

from src.ingestion.eurlex_discovery import (
    CATEGORY_RULES,
    EXCLUDE_TITLE_PATTERNS,
    WEAK_EXCLUDE_PATTERNS,
    _normalize,
    classify_regulation,
    filter_candidates,
)


# --- _normalize ---


class TestNormalize:
    """Test whitespace normalization."""

    def test_regular_spaces(self):
        assert _normalize("hello world") == "hello world"

    def test_non_breaking_spaces(self):
        assert _normalize("Regulation\xa0(EU)\xa02017/625") == "Regulation (EU) 2017/625"

    def test_mixed_whitespace(self):
        assert _normalize("a \t b  \n c") == "a b c"

    def test_strips_edges(self):
        assert _normalize("  padded  ") == "padded"


# --- classify_regulation ---


class TestClassifyRegulation:
    """Test category assignment from regulation titles."""

    def test_novel_food(self):
        title = "Regulation (EU) 2015/2283 on novel foods, amending Regulation (EC) No 258/97"
        assert classify_regulation(title) == "novel_food"

    def test_food_additives(self):
        title = "Regulation (EC) No 1333/2008 on food additives"
        assert classify_regulation(title) == "food_additives"

    def test_food_contact_materials(self):
        title = "Regulation (EC) No 1935/2004 on materials and articles intended to come into contact with food"
        assert classify_regulation(title) == "food_contact_materials"

    def test_labelling_fic(self):
        title = "Regulation (EU) No 1169/2011 on the provision of food information to consumers"
        assert classify_regulation(title) == "labelling_fic"

    def test_official_controls(self):
        title = "Regulation (EU) 2017/625 on official controls and other official activities"
        assert classify_regulation(title) == "official_controls"

    def test_official_controls_2017_625_supplement(self):
        title = "Commission Delegated Regulation (EU) 2019/625 supplementing Regulation (EU) 2017/625"
        assert classify_regulation(title) == "official_controls"

    def test_general_food_law(self):
        title = "Regulation (EC) No 178/2002 laying down the general principles and requirements of food law"
        assert classify_regulation(title) == "general_food_law"

    def test_contaminants(self):
        title = "Commission Regulation (EU) 2023/915 on maximum levels for certain contaminants in food"
        assert classify_regulation(title) == "contaminants"

    def test_gmo(self):
        title = "Regulation (EC) No 1829/2003 on genetically modified food and feed"
        assert classify_regulation(title) == "gmo"

    def test_organic(self):
        title = "Regulation (EU) 2018/848 on organic production and labelling of organic products"
        assert classify_regulation(title) == "organic"

    def test_food_specific_groups(self):
        title = "Regulation (EU) No 609/2013 on food intended for infants and young children"
        assert classify_regulation(title) == "food_specific_groups"

    def test_sweeteners_as_food_additives(self):
        title = "Directive 94/35/EC on sweeteners for use in foodstuffs"
        assert classify_regulation(title) == "food_additives"

    def test_colours_as_food_additives(self):
        title = "Directive 94/36/EC on colours for use in foodstuffs"
        assert classify_regulation(title) == "food_additives"

    def test_product_standards_honey(self):
        title = "Council Directive 2001/110/EC relating to honey"
        assert classify_regulation(title) == "product_standards"

    def test_pesticide_mrls_as_contaminants(self):
        title = "Regulation (EC) No 396/2005 on maximum residue levels of pesticides in food"
        assert classify_regulation(title) == "contaminants"

    def test_unclassified_fallback(self):
        title = "Some regulation that doesn't match any category"
        assert classify_regulation(title) == "unclassified"

    def test_non_breaking_space_in_title(self):
        """Ensure titles with non-breaking spaces still match patterns."""
        # This simulates what EUR-Lex returns — \xa0 between (EU) and number
        title = "Commission Delegated Regulation (EU)\xa02019/625 supplementing Regulation (EU)\xa02017/625"
        assert classify_regulation(title) == "official_controls"


# --- filter_candidates ---


class TestFilterCandidates:
    """Test the two-tier filtering logic."""

    def _make_candidate(self, celex: str, title: str) -> dict:
        return {"celex": celex, "title": title, "directory_codes": []}

    def test_keeps_normal_regulation(self):
        candidates = [self._make_candidate(
            "32008R1333",
            "Regulation (EC) No 1333/2008 on food additives",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 1

    def test_excludes_strong_pattern(self):
        """Strong excludes always filter, even if a category would match."""
        candidates = [self._make_candidate(
            "32020R0466",
            "Commission Regulation (EU) 2020/466 on emergency measures relating to food additives",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 0

    def test_excludes_non_food_sector(self):
        candidates = [self._make_candidate(
            "32009L0048",
            "Directive 2009/48/EC on the safety of toys",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 0

    def test_excludes_amendment_only_act(self):
        """Pure amendments (no substantive content before 'amending') are excluded."""
        candidates = [self._make_candidate(
            "32017R1257",
            "Commission Regulation (EU) 2017/1257 of 14 July 2017 amending Annex I to Regulation (EC) No 1334/2008",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 0

    def test_keeps_framework_reg_with_amending(self):
        """Framework regulations with ', amending' in the title are kept."""
        candidates = [self._make_candidate(
            "32015R2283",
            "Regulation (EU) 2015/2283 on novel foods, amending Regulation (EC) No 258/97",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 1

    def test_keeps_framework_reg_with_and_amending(self):
        """Framework regulations with 'and amending' in the title are kept."""
        candidates = [self._make_candidate(
            "32003R1830",
            "Regulation (EC) No 1830/2003 concerning the traceability and labelling of genetically modified organisms and amending Directive 2001/18/EC",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 1

    def test_keeps_framework_reg_with_and_repealing(self):
        """Framework regulations with 'and repealing' are kept."""
        candidates = [self._make_candidate(
            "32023R0915",
            "Commission Regulation (EU) 2023/915 on maximum levels for certain contaminants in food and repealing Regulation (EC) No 1881/2006",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 1

    def test_excludes_non_rl_document_type(self):
        """Only Regulations (R) and Directives (L) are kept."""
        candidates = [self._make_candidate(
            "32002D0657",  # Decision (D)
            "Council Decision 2002/657/EC on analytical methods for residues",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 0

    def test_excludes_corrigendum_celex(self):
        """CELEX IDs containing R(01) etc. (corrigenda) are excluded."""
        candidates = [self._make_candidate(
            "32008R1333R(01)",
            "Corrigendum to Regulation (EC) No 1333/2008 on food additives",
        )]
        result = filter_candidates(candidates)
        assert len(result) == 0


# --- Pattern consistency ---


class TestPatternConsistency:
    """Ensure patterns are well-formed and don't overlap problematically."""

    def test_exclude_patterns_are_lowercase(self):
        """All exclude patterns should be lowercase for case-insensitive matching."""
        for pattern in EXCLUDE_TITLE_PATTERNS:
            assert pattern == pattern.lower(), f"Pattern not lowercase: {pattern!r}"

    def test_weak_exclude_patterns_are_lowercase(self):
        for pattern in WEAK_EXCLUDE_PATTERNS:
            assert pattern == pattern.lower(), f"Pattern not lowercase: {pattern!r}"

    def test_category_rule_patterns_are_lowercase(self):
        for pattern, category in CATEGORY_RULES:
            assert pattern == pattern.lower(), f"Pattern not lowercase: {pattern!r}"

    def test_no_duplicate_exclude_patterns(self):
        assert len(EXCLUDE_TITLE_PATTERNS) == len(set(EXCLUDE_TITLE_PATTERNS))

    def test_no_duplicate_category_rules(self):
        patterns = [p for p, _ in CATEGORY_RULES]
        assert len(patterns) == len(set(patterns))

    def test_known_categories_are_valid(self):
        """All categories in rules should be from the known set."""
        known = {
            "food_specific_groups", "novel_food", "food_supplements", "food_additives",
            "flavourings", "food_enzymes", "food_contact_materials", "labelling_fic",
            "nutrition_health_claims", "contaminants", "official_controls", "organic",
            "gmo", "fortification", "feed", "food_irradiation", "general_food_law",
            "product_standards",
        }
        for _, category in CATEGORY_RULES:
            assert category in known, f"Unknown category: {category!r}"
