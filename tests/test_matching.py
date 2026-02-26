"""
Unit tests for the extraction evaluation matching engine.

All tests use synthetic data — no LLM calls, no cache files needed.
"""

import pytest

from src.evaluation.matching import (
    _is_partial_match,
    _match_key,
    _significant_words,
    _word_overlap,
    match_requirements,
)
from src.evaluation.schemas import GroundTruthRequirement, MatchResult


def _gt(
    req_id: str,
    reg: str = "32015R2283",
    art: int = 7,
    rtype: str = "authorisation",
    desc: str = "Novel food must be authorised before market placement",
    priority: str = "before_launch",
) -> GroundTruthRequirement:
    """Helper to create ground truth requirements."""
    return GroundTruthRequirement(
        requirement_id=req_id,
        regulation_id=reg,
        article_number=art,
        requirement_type=rtype,
        description=desc,
        priority=priority,
        source="test",
    )


def _ext(
    reg: str = "32015R2283",
    art: int = 7,
    rtype: str = "authorisation",
    summary: str = "Novel food must be authorised before placing on the EU market",
) -> dict:
    """Helper to create extracted requirement dicts."""
    return {
        "regulation_id": reg,
        "article_number": art,
        "requirement_type": rtype,
        "requirement_summary": summary,
        "confidence": 0.9,
    }


# --- Match key tests ---


class TestMatchKey:
    def test_key_from_dict(self):
        key = _match_key(_ext())
        assert key == ("32015R2283", 7, "authorisation")

    def test_key_from_ground_truth(self):
        key = _match_key(_gt("NF-01"))
        assert key == ("32015R2283", 7, "authorisation")

    def test_different_regulation_different_key(self):
        assert _match_key(_ext(reg="32002R0178")) != _match_key(_gt("NF-01"))

    def test_different_article_different_key(self):
        assert _match_key(_ext(art=10)) != _match_key(_gt("NF-01"))


# --- Word overlap tests ---


class TestWordOverlap:
    def test_identical_texts(self):
        assert _word_overlap("food safety regulation", "food safety regulation") == 3

    def test_stopwords_excluded(self):
        words = _significant_words("the food is on the market")
        assert "the" not in words
        assert "food" in words
        assert "market" in words

    def test_partial_overlap(self):
        overlap = _word_overlap(
            "food business operators must establish traceability",
            "traceability requirements for food operators",
        )
        assert overlap >= 3  # food, operators, traceability

    def test_no_overlap(self):
        assert _word_overlap("alpha beta gamma", "delta epsilon zeta") == 0


# --- Partial match tests ---


class TestPartialMatch:
    def test_type_mismatch_with_word_overlap(self):
        ext = _ext(rtype="general_obligation")
        gt = _gt("NF-01", rtype="authorisation")
        is_match, reason = _is_partial_match(ext, gt)
        assert is_match
        assert "requirement_type" in reason

    def test_type_mismatch_without_overlap(self):
        ext = _ext(rtype="general_obligation", summary="completely unrelated text xyz")
        gt = _gt("NF-01", desc="novel food authorisation required")
        is_match, _ = _is_partial_match(ext, gt)
        assert not is_match

    def test_two_field_mismatch_no_match(self):
        ext = _ext(reg="32002R0178", rtype="traceability")
        gt = _gt("NF-01")
        is_match, _ = _is_partial_match(ext, gt)
        assert not is_match

    def test_article_mismatch_with_overlap(self):
        ext = _ext(art=6, summary="novel food must be authorised before market placement")
        gt = _gt("NF-01", art=7, desc="novel food must be authorised before market placement")
        is_match, reason = _is_partial_match(ext, gt)
        assert is_match
        assert "article_number" in reason


# --- Full matching tests ---


class TestMatchRequirements:
    def test_perfect_match(self):
        gt = [_gt("NF-01"), _gt("NF-02", art=10, rtype="documentation")]
        extracted = [_ext(), _ext(art=10, rtype="documentation")]
        result = match_requirements(extracted, gt)
        assert len(result.true_positives) == 2
        assert len(result.false_positives) == 0
        assert len(result.false_negatives) == 0
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_empty_extraction(self):
        gt = [_gt("NF-01"), _gt("NF-02", art=10)]
        result = match_requirements([], gt)
        assert len(result.true_positives) == 0
        assert len(result.false_negatives) == 2
        assert result.precision == 0.0
        assert result.recall == 0.0

    def test_all_false_positives(self):
        gt = [_gt("NF-01")]
        extracted = [_ext(reg="32002R0178", art=18, rtype="traceability")]
        result = match_requirements(extracted, gt)
        assert len(result.true_positives) == 0
        assert len(result.false_positives) == 1
        assert len(result.false_negatives) == 1

    def test_mixed_results(self):
        gt = [
            _gt("NF-01"),
            _gt("NF-02", art=10, rtype="documentation"),
            _gt("NF-03", art=18, reg="32002R0178", rtype="traceability"),
        ]
        extracted = [
            _ext(),  # matches NF-01
            _ext(art=99, rtype="labelling"),  # FP — no match
        ]
        result = match_requirements(extracted, gt)
        assert len(result.true_positives) == 1
        assert len(result.false_positives) == 1
        assert len(result.false_negatives) == 2

    def test_one_to_one_constraint(self):
        """Two extracted requirements for one ground truth = 1 TP + 1 FP."""
        gt = [_gt("NF-01")]
        extracted = [_ext(), _ext()]  # both match same key
        result = match_requirements(extracted, gt)
        assert len(result.true_positives) == 1
        assert len(result.false_positives) == 1

    def test_partial_match_counted(self):
        gt = [_gt("NF-01", rtype="authorisation")]
        extracted = [_ext(rtype="general_obligation")]  # type mismatch, words overlap
        result = match_requirements(extracted, gt, allow_partial=True)
        assert len(result.partial_matches) == 1
        assert len(result.false_positives) == 0
        assert len(result.false_negatives) == 0
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_partial_match_disabled(self):
        gt = [_gt("NF-01", rtype="authorisation")]
        extracted = [_ext(rtype="general_obligation")]
        result = match_requirements(extracted, gt, allow_partial=False)
        assert len(result.partial_matches) == 0
        assert len(result.false_positives) == 1
        assert len(result.false_negatives) == 1

    def test_exact_match_preferred_over_partial(self):
        """Exact matches should be resolved first, leaving partial for the rest."""
        gt = [
            _gt("NF-01", rtype="authorisation"),
            _gt("NF-02", art=10, rtype="documentation",
                 desc="application submission documentation requirements for novel food"),
        ]
        extracted = [
            _ext(),  # exact match for NF-01
            _ext(art=10, rtype="general_obligation",
                 summary="documentation application submission required for novel food"),
        ]
        result = match_requirements(extracted, gt)
        assert len(result.true_positives) == 1
        assert len(result.partial_matches) == 1

    def test_precision_recall_computation(self):
        gt = [
            _gt("NF-0", art=7, rtype="authorisation"),
            _gt("NF-1", art=10, rtype="documentation", desc="submit dossier to EFSA"),
            _gt("NF-2", art=18, reg="32002R0178", rtype="traceability", desc="establish traceability"),
            _gt("NF-3", art=9, rtype="labelling", desc="specific labelling conditions"),
        ]
        # 1 exact match, 2 FP, 3 FN
        extracted = [
            _ext(art=7, rtype="authorisation"),  # matches NF-0
            _ext(art=7, rtype="authorisation"),  # duplicate → FP (key already consumed)
            _ext(reg="XXXXX", art=99, rtype="labelling"),  # FP
        ]
        result = match_requirements(extracted, gt, allow_partial=False)
        assert len(result.true_positives) == 1
        assert len(result.false_positives) == 2
        assert len(result.false_negatives) == 3
        assert result.precision == pytest.approx(1 / 3, abs=0.01)
        assert result.recall == pytest.approx(1 / 4, abs=0.01)


# --- MatchResult property tests ---


class TestMatchResultProperties:
    def test_f1_perfect(self):
        result = MatchResult(
            true_positives=[(_gt("NF-01"), _ext())],
        )
        assert result.f1 == 1.0

    def test_f1_zero(self):
        result = MatchResult()
        assert result.f1 == 0.0

    def test_precision_with_partials(self):
        result = MatchResult(
            true_positives=[(_gt("NF-01"), _ext())],
            partial_matches=[(_gt("NF-02"), _ext(), "type mismatch")],
            false_positives=[_ext()],
        )
        # (1 + 1) / (1 + 1 + 1) = 2/3
        assert result.precision == pytest.approx(2 / 3, abs=0.01)
