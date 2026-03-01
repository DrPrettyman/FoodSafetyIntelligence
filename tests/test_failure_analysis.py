"""
Unit tests for the failure mode analysis module.

All tests use synthetic data — no LLM calls, no cache files needed.
"""

import json

import pytest

from src.evaluation.failure_analysis import (
    AggregateFailureAnalysis,
    ErrorCategory,
    FPCategory,
    FNDiagnosis,
    FPDiagnosis,
    ScenarioFailureAnalysis,
    analyze_scenario,
    classify_false_negative,
    classify_false_positive,
    format_failure_report,
)
from src.evaluation.matching import match_requirements
from src.evaluation.schemas import GroundTruthRequirement, MatchResult


# --- Helpers (reuse _gt / _ext pattern from test_matching.py) ---


def _gt(
    req_id: str,
    reg: str = "32015R2283",
    art: int = 7,
    rtype: str = "authorisation",
    desc: str = "Novel food must be authorised before market placement",
    priority: str = "before_launch",
) -> GroundTruthRequirement:
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
    confidence: float = 0.9,
    applicable_to: str = "Food business operators",
    conditions: str = "",
) -> dict:
    return {
        "regulation_id": reg,
        "article_number": art,
        "requirement_type": rtype,
        "requirement_summary": summary,
        "confidence": confidence,
        "applicable_to": applicable_to,
        "conditions": conditions,
        "source_text_snippet": "test source text",
    }


def _pipeline_output(
    routed_celex: list[str] | None = None,
    reasons: dict[str, list[str]] | None = None,
    articles: list[dict] | None = None,
    requirements: list[dict] | None = None,
    expanded_celex_ids: list[str] | None = None,
) -> dict:
    """Build a synthetic pipeline_output dict matching the cached structure."""
    return {
        "routing": {
            "celex_ids": routed_celex or [],
            "reasons": reasons or {},
            "regulation_count": len(routed_celex or []),
            "cross_references": {
                "expanded_count": len(expanded_celex_ids or []),
                "expanded_celex_ids": expanded_celex_ids or [],
                "resolved_refs": 0,
                "unresolved_refs": 0,
            },
        },
        "retrieval": {
            "query": "test query",
            "results_count": len(articles or []),
            "articles": articles or [],
        },
        "extraction": {
            "requirements": requirements or [],
            "requirements_count": len(requirements or []),
            "articles_processed": 5,
        },
    }


def _article(celex: str, art_num: int, score: float = 0.5) -> dict:
    """Build a synthetic retrieved article entry."""
    return {
        "chunk_id": f"{celex}_art{art_num}_chunk0",
        "text": f"Article {art_num} text...",
        "metadata": {
            "celex_id": celex,
            "article_number": art_num,
            "article_title": f"Article {art_num}",
            "chapter": "",
            "section": "",
            "chunk_index": 0,
            "total_chunks": 1,
        },
        "score": score,
    }


# --- FN classification tests ---


class TestClassifyFalseNegative:
    def test_retrieval_failure_routed_not_retrieved(self):
        """Regulation routed but article not in retrieval results."""
        fn = _gt("NF-01", reg="32015R2283", art=6)
        output = _pipeline_output(
            routed_celex=["32015R2283", "32002R0178"],
            articles=[_article("32015R2283", 10)],  # Art 10 retrieved, not Art 6
            requirements=[_ext(reg="32015R2283", art=10)],
        )
        diag = classify_false_negative(fn, output)

        assert diag.error_category == ErrorCategory.RETRIEVAL_FAILURE
        assert diag.was_routed is True
        assert diag.was_retrieved is False
        assert "Art 6 not in retrieved articles" in diag.explanation

    def test_routing_miss_not_routed(self):
        """Regulation not in routed set at all."""
        fn = _gt("NF-02", reg="32006R1924", art=5)
        output = _pipeline_output(
            routed_celex=["32015R2283", "32002R0178"],
        )
        diag = classify_false_negative(fn, output)

        assert diag.error_category == ErrorCategory.ROUTING_MISS
        assert diag.was_routed is False
        assert diag.was_retrieved is False
        assert "not in routed set" in diag.explanation

    def test_extraction_failure_retrieved_not_extracted(self):
        """Article retrieved but not extracted by LLM."""
        fn = _gt("NF-03", reg="32015R2283", art=6, rtype="authorisation")
        output = _pipeline_output(
            routed_celex=["32015R2283"],
            articles=[_article("32015R2283", 6)],  # Art 6 retrieved
            requirements=[_ext(reg="32015R2283", art=10)],  # But only Art 10 extracted
        )
        diag = classify_false_negative(fn, output)

        assert diag.error_category == ErrorCategory.EXTRACTION_FAILURE
        assert diag.was_routed is True
        assert diag.was_retrieved is True
        assert "retrieved but not extracted" in diag.explanation

    def test_extraction_failure_matching_mismatch(self):
        """Article retrieved and extracted but matching failed (type mismatch)."""
        fn = _gt("NF-04", reg="32015R2283", art=6, rtype="authorisation")
        output = _pipeline_output(
            routed_celex=["32015R2283"],
            articles=[_article("32015R2283", 6)],
            # Extracted from Art 6 but with different type — matching won't catch it
            requirements=[_ext(reg="32015R2283", art=6, rtype="notification")],
        )
        diag = classify_false_negative(fn, output)

        assert diag.error_category == ErrorCategory.EXTRACTION_FAILURE
        assert diag.was_routed is True
        assert diag.was_retrieved is True
        assert "matching failed" in diag.explanation

    def test_retrieval_failure_no_articles_from_regulation(self):
        """Regulation routed but zero articles retrieved from it."""
        fn = _gt("NF-05", reg="32015R2283", art=6)
        output = _pipeline_output(
            routed_celex=["32015R2283", "32002R0178"],
            articles=[_article("32002R0178", 18)],  # Only other reg retrieved
            requirements=[_ext(reg="32002R0178", art=18, rtype="traceability")],
        )
        diag = classify_false_negative(fn, output)

        assert diag.error_category == ErrorCategory.RETRIEVAL_FAILURE
        assert "routed but no articles retrieved" in diag.explanation


# --- FP classification tests ---


class TestClassifyFalsePositive:
    def test_tangential_cross_ref(self):
        """FP from a cross-reference-expanded regulation."""
        fp = _ext(reg="32008R1332", art=11, rtype="labelling")
        output = _pipeline_output(
            routed_celex=["32015R2283", "32008R1332"],
            reasons={
                "32015R2283": ["product type: novel food"],
                "32008R1332": ["cross-referenced from 32015R2283"],
            },
        )
        diag = classify_false_positive(fp, output, "novel food")

        assert diag.fp_category == FPCategory.TANGENTIAL_CROSS_REF
        assert diag.is_cross_ref_expansion is True
        assert "cross-reference" in diag.explanation

    def test_scope_error_wrong_product(self):
        """FP with applicable_to mentioning a different product domain."""
        fp = _ext(
            reg="32003R1829", art=13, rtype="labelling",
            applicable_to="GMO food products",
            conditions="Products containing genetically modified organisms",
        )
        output = _pipeline_output(
            routed_celex=["32015R2283", "32003R1829"],
            reasons={
                "32015R2283": ["product type: novel food"],
                "32003R1829": ["keyword: gmo"],
            },
        )
        diag = classify_false_positive(fp, output, "novel food")

        assert diag.fp_category == FPCategory.SCOPE_ERROR
        assert "gmo" in diag.explanation.lower() or "genetically modified" in diag.explanation.lower()

    def test_hallucination_not_in_routed_set(self):
        """FP references a regulation not in the routed set."""
        fp = _ext(reg="32099R9999", art=1, rtype="authorisation")
        output = _pipeline_output(
            routed_celex=["32015R2283", "32002R0178"],
        )
        diag = classify_false_positive(fp, output, "novel food")

        assert diag.fp_category == FPCategory.HALLUCINATION
        assert diag.is_cross_ref_expansion is False
        assert "not in routed set" in diag.explanation

    def test_over_extraction_default(self):
        """Generic valid extraction with no domain mismatch → over_extraction."""
        fp = _ext(
            reg="32002R0178", art=17, rtype="general_obligation",
            applicable_to="Food business operators",
        )
        output = _pipeline_output(
            routed_celex=["32015R2283", "32002R0178"],
            reasons={
                "32002R0178": ["always included (General Food Law)"],
            },
        )
        diag = classify_false_positive(fp, output, "novel food")

        assert diag.fp_category == FPCategory.OVER_EXTRACTION
        assert diag.is_cross_ref_expansion is False
        assert "not covered by ground truth" in diag.explanation

    def test_scope_error_enzyme_in_food_scenario(self):
        """FP about food enzymes in a general food labelling scenario."""
        fp = _ext(
            reg="32008R1332", art=10, rtype="labelling",
            applicable_to="Food enzyme preparations",
        )
        output = _pipeline_output(
            routed_celex=["32011R1169", "32008R1332"],
            reasons={
                "32008R1332": ["keyword: enzyme"],
            },
        )
        diag = classify_false_positive(fp, output, "")

        assert diag.fp_category == FPCategory.SCOPE_ERROR
        assert "enzyme" in diag.explanation


# --- Scenario analysis tests ---


class TestAnalyzeScenario:
    def test_fn_diagnoses_count_matches(self):
        """FN diagnoses count should equal FN count from matching."""
        gt = [_gt("NF-01", art=6), _gt("NF-02", art=7)]
        extracted = [_ext(art=10)]  # Neither matches
        result = match_requirements(extracted, gt)

        output = _pipeline_output(
            routed_celex=["32015R2283"],
            articles=[_article("32015R2283", 10)],
            requirements=[_ext(art=10)],
        )
        analysis = analyze_scenario("test", result, output, "novel food")

        assert len(analysis.fn_diagnoses) == len(result.false_negatives)

    def test_fp_diagnoses_count_matches(self):
        """FP diagnoses count should equal FP count from matching."""
        gt = [_gt("NF-01")]
        extracted = [
            _ext(),  # This matches NF-01
            _ext(reg="32002R0178", art=18, rtype="traceability"),  # FP
            _ext(reg="32002R0178", art=19, rtype="general_obligation"),  # FP
        ]
        result = match_requirements(extracted, gt)

        output = _pipeline_output(
            routed_celex=["32015R2283", "32002R0178"],
            reasons={"32002R0178": ["always included"]},
        )
        analysis = analyze_scenario("test", result, output, "novel food")

        assert len(analysis.fp_diagnoses) == len(result.false_positives)

    def test_to_dict_serializable(self):
        """Serialization should produce valid JSON-compatible dict."""
        gt = [_gt("NF-01", art=6)]
        extracted = [_ext(art=10)]
        result = match_requirements(extracted, gt)

        output = _pipeline_output(
            routed_celex=["32015R2283"],
            articles=[_article("32015R2283", 10)],
            requirements=[_ext(art=10)],
        )
        analysis = analyze_scenario("test", result, output)
        d = analysis.to_dict()

        # Should be JSON-serializable
        serialized = json.dumps(d, default=str)
        assert isinstance(json.loads(serialized), dict)
        assert d["scenario_id"] == "test"
        assert d["fn_count"] == len(result.false_negatives)
        assert d["fp_count"] == len(result.false_positives)


# --- Aggregate analysis tests ---


class TestAggregateAnalysis:
    def test_totals_sum_correctly(self):
        """Aggregate counts should equal sum of per-scenario counts."""
        # Scenario A: 2 FN, 1 FP
        s_a = ScenarioFailureAnalysis(
            scenario_id="scenario_a",
            fn_diagnoses=[
                FNDiagnosis(_gt("A-1"), ErrorCategory.RETRIEVAL_FAILURE, True, False, "test"),
                FNDiagnosis(_gt("A-2"), ErrorCategory.ROUTING_MISS, False, False, "test"),
            ],
            fp_diagnoses=[
                FPDiagnosis(_ext(), FPCategory.OVER_EXTRACTION, False, 0.8, "test"),
            ],
        )
        # Scenario B: 1 FN, 2 FP
        s_b = ScenarioFailureAnalysis(
            scenario_id="scenario_b",
            fn_diagnoses=[
                FNDiagnosis(_gt("B-1"), ErrorCategory.RETRIEVAL_FAILURE, True, False, "test"),
            ],
            fp_diagnoses=[
                FPDiagnosis(_ext(), FPCategory.TANGENTIAL_CROSS_REF, True, 0.7, "test"),
                FPDiagnosis(_ext(), FPCategory.SCOPE_ERROR, False, 0.5, "test"),
            ],
        )

        agg = AggregateFailureAnalysis(scenarios=[s_a, s_b])

        assert agg.total_fn == 3
        assert agg.total_fp == 3
        assert agg.total_fn_by_category[ErrorCategory.RETRIEVAL_FAILURE.value] == 2
        assert agg.total_fn_by_category[ErrorCategory.ROUTING_MISS.value] == 1
        assert agg.total_fp_by_category[FPCategory.OVER_EXTRACTION.value] == 1
        assert agg.total_fp_by_category[FPCategory.TANGENTIAL_CROSS_REF.value] == 1
        assert agg.total_fp_by_category[FPCategory.SCOPE_ERROR.value] == 1

    def test_to_dict_has_summary(self):
        """Aggregate to_dict should include summary with totals."""
        agg = AggregateFailureAnalysis(scenarios=[
            ScenarioFailureAnalysis(scenario_id="test"),
        ])
        d = agg.to_dict()

        assert "summary" in d
        assert "total_fn" in d["summary"]
        assert "total_fp" in d["summary"]
        assert "per_scenario" in d
        assert "test" in d["per_scenario"]


# --- Report formatting tests ---


class TestFormatReport:
    @pytest.fixture
    def sample_analysis(self):
        s = ScenarioFailureAnalysis(
            scenario_id="novel_food_insect_protein",
            fn_diagnoses=[
                FNDiagnosis(
                    _gt("NF-01", art=6), ErrorCategory.RETRIEVAL_FAILURE,
                    True, False, "Art 6 not retrieved by vector search",
                ),
            ],
            fp_diagnoses=[
                FPDiagnosis(
                    _ext(reg="32008R1332", art=11), FPCategory.TANGENTIAL_CROSS_REF,
                    True, 0.7, "From cross-reference expansion",
                ),
            ],
        )
        return AggregateFailureAnalysis(scenarios=[s])

    def test_contains_summary_tables(self, sample_analysis):
        report = format_failure_report(sample_analysis)
        assert "False Negative Distribution" in report
        assert "False Positive Distribution" in report
        assert "retrieval_failure" in report
        assert "tangential_cross_ref" in report

    def test_contains_per_scenario_sections(self, sample_analysis):
        report = format_failure_report(sample_analysis)
        assert "novel_food_insect_protein" in report
        assert "NF-01" in report
        assert "Key Findings" in report
