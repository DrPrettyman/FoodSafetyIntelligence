"""
Unit tests for cross-reference resolution.

All tests use synthetic data — no LLM, no filesystem dependencies.
"""

import pytest

from src.extraction.entity_extractor import CrossReference
from src.retrieval.cross_references import CrossReferenceIndex, regulation_number_to_celex


# --- regulation_number_to_celex ---


class TestRegulationNumberToCelex:
    """Test human-readable regulation number → CELEX ID mapping."""

    def test_old_style_regulation(self):
        """Old-style: '178/2002' → 32002R0178."""
        corpus = {"32002R0178", "32011R1169"}
        assert regulation_number_to_celex("178/2002", corpus) == "32002R0178"

    def test_new_style_regulation(self):
        """New-style: '2015/2283' → 32015R2283."""
        corpus = {"32015R2283", "32002R0178"}
        assert regulation_number_to_celex("2015/2283", corpus) == "32015R2283"

    def test_directive(self):
        """Directive: '46/2002' → 32002L0046 (L prefix)."""
        corpus = {"32002L0046", "32002R0178"}
        assert regulation_number_to_celex("46/2002", corpus) == "32002L0046"

    def test_not_in_corpus(self):
        """Returns None for regulation numbers not in corpus."""
        corpus = {"32002R0178"}
        assert regulation_number_to_celex("999/2020", corpus) is None

    def test_invalid_format(self):
        """Returns None for malformed input."""
        corpus = {"32002R0178"}
        assert regulation_number_to_celex("bad", corpus) is None
        assert regulation_number_to_celex("", corpus) is None
        assert regulation_number_to_celex("abc/def", corpus) is None

    def test_three_digit_number(self):
        """Three-digit regulation number: '852/2004' → 32004R0852."""
        corpus = {"32004R0852"}
        assert regulation_number_to_celex("852/2004", corpus) == "32004R0852"

    def test_four_digit_number(self):
        """Four-digit number: '1169/2011' → 32011R1169."""
        corpus = {"32011R1169"}
        assert regulation_number_to_celex("1169/2011", corpus) == "32011R1169"


# --- CrossReferenceIndex.build ---


class TestCrossReferenceIndexBuild:
    """Test building the cross-reference index."""

    def test_resolves_in_corpus_targets(self):
        refs = [
            CrossReference("32015R2283", 3, "178/2002", "...references..."),
            CrossReference("32015R2283", 5, "1169/2011", "...references..."),
        ]
        corpus = {"32002R0178", "32011R1169", "32015R2283"}
        idx = CrossReferenceIndex.build(refs, corpus)

        assert idx.resolved_count == 2
        assert idx.unresolved_count == 0

    def test_tracks_unresolved_targets(self):
        refs = [
            CrossReference("32015R2283", 3, "178/2002", "..."),
            CrossReference("32015R2283", 5, "999/2020", "..."),
        ]
        corpus = {"32002R0178", "32015R2283"}
        idx = CrossReferenceIndex.build(refs, corpus)

        assert idx.resolved_count == 1
        assert idx.unresolved_count == 1

    def test_self_references_excluded(self):
        """A regulation referencing itself should not create a link."""
        refs = [
            CrossReference("32002R0178", 5, "178/2002", "..."),
        ]
        corpus = {"32002R0178"}
        idx = CrossReferenceIndex.build(refs, corpus)

        assert idx.resolved_count == 0

    def test_empty_input(self):
        idx = CrossReferenceIndex.build([], {"32002R0178"})
        assert idx.resolved_count == 0
        assert idx.unresolved_count == 0


# --- CrossReferenceIndex.expand ---


class TestCrossReferenceIndexExpand:
    """Test 1-hop expansion of CELEX ID sets."""

    @pytest.fixture()
    def sample_index(self):
        """Index where 32015R2283 references 32002R0178 and 32011R1169."""
        refs = [
            CrossReference("32015R2283", 3, "178/2002", "..."),
            CrossReference("32015R2283", 5, "1169/2011", "..."),
            CrossReference("32002L0046", 8, "178/2002", "..."),
        ]
        corpus = {"32002R0178", "32011R1169", "32015R2283", "32002L0046"}
        return CrossReferenceIndex.build(refs, corpus)

    def test_single_source_expansion(self, sample_index):
        new_ids, reasons = sample_index.expand(["32015R2283"])
        assert set(new_ids) == {"32002R0178", "32011R1169"}
        assert "32002R0178" in reasons
        assert "32011R1169" in reasons

    def test_already_included_not_duplicated(self, sample_index):
        """If a target is already in the input, it's not added again."""
        new_ids, reasons = sample_index.expand(["32015R2283", "32002R0178"])
        assert "32002R0178" not in new_ids
        assert "32011R1169" in new_ids

    def test_empty_input(self, sample_index):
        new_ids, reasons = sample_index.expand([])
        assert new_ids == []
        assert reasons == {}

    def test_no_cross_refs_for_source(self, sample_index):
        """Source with no cross-references returns nothing."""
        new_ids, reasons = sample_index.expand(["32011R1169"])
        assert new_ids == []

    def test_multiple_sources_union(self, sample_index):
        """Multiple sources: union of targets, deduplicated."""
        new_ids, reasons = sample_index.expand(["32015R2283", "32002L0046"])
        # Both reference 32002R0178; 32015R2283 also references 32011R1169
        assert set(new_ids) == {"32002R0178", "32011R1169"}

    def test_reasons_populated(self, sample_index):
        new_ids, reasons = sample_index.expand(["32015R2283"])
        for cid in new_ids:
            assert len(reasons[cid]) >= 1
            assert "cross-referenced from 32015R2283" in reasons[cid]

    def test_multiple_sources_reason_aggregation(self, sample_index):
        """Target referenced by multiple sources gets multiple reasons."""
        new_ids, reasons = sample_index.expand(["32015R2283", "32002L0046"])
        # 32002R0178 is referenced by both sources
        assert "cross-referenced from 32015R2283" in reasons["32002R0178"]
        assert "cross-referenced from 32002L0046" in reasons["32002R0178"]
