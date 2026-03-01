"""
Layer 3 evaluation: extraction quality against ground truth checklists.

Reads cached pipeline results and compares extracted requirements against
ground truth checklists. Skips if no cache files exist.

To populate the cache:
    python scripts/run_extraction_scenarios.py --provider claude-code
"""

import json
from pathlib import Path

import pytest

from src.evaluation.matching import match_requirements
from src.evaluation.metrics import (
    compute_aggregate_metrics,
    compute_scenario_metrics,
    format_scenario_report,
)
from src.evaluation.schemas import EvaluationScenario, MatchResult

GT_DIR = Path("data/evaluation/ground_truth")
CACHE_DIR = Path("data/evaluation/cache")

has_cache = CACHE_DIR.exists() and any(CACHE_DIR.glob("*_run_*.json"))


def _load_evaluation_data() -> dict[str, tuple[EvaluationScenario, dict]]:
    """Load ground truth and most recent cached results for each scenario."""
    data = {}

    for gt_path in sorted(GT_DIR.glob("scenario_*.json")):
        scenario = EvaluationScenario.from_json(gt_path)

        # Find most recent cache file for this scenario
        cache_files = sorted(CACHE_DIR.glob(f"{scenario.scenario_id}_run_*.json"))
        if not cache_files:
            continue

        with open(cache_files[-1]) as f:
            cache_entry = json.load(f)

        data[scenario.scenario_id] = (scenario, cache_entry["pipeline_output"])

    return data


def _run_matching(scenario: EvaluationScenario, output: dict) -> MatchResult:
    """Run matching for a scenario against its cached output."""
    extracted = output.get("extraction", {}).get("requirements", [])
    return match_requirements(extracted, scenario.requirements)


@pytest.fixture(scope="module")
def evaluation_data():
    """Load all ground truth + cached extraction results."""
    return _load_evaluation_data()


@pytest.mark.skipif(not has_cache, reason="No cached extraction results")
class TestExtractionQuality:
    """Per-scenario and aggregate extraction quality tests."""

    def test_novel_food_precision(self, evaluation_data):
        scenario, output = evaluation_data["novel_food_insect_protein"]
        result = _run_matching(scenario, output)
        print("\n" + format_scenario_report(scenario.scenario_id, result))
        assert result.precision >= 0.30, (
            f"Novel food precision {result.precision:.2f} < 0.30"
        )

    def test_novel_food_recall(self, evaluation_data):
        scenario, output = evaluation_data["novel_food_insect_protein"]
        result = _run_matching(scenario, output)
        assert result.recall >= 0.40, (
            f"Novel food recall {result.recall:.2f} < 0.40"
        )

    def test_fic_labelling_precision(self, evaluation_data):
        scenario, output = evaluation_data["fic_labelling_general"]
        result = _run_matching(scenario, output)
        print("\n" + format_scenario_report(scenario.scenario_id, result))
        assert result.precision >= 0.30, (
            f"FIC labelling precision {result.precision:.2f} < 0.30"
        )

    def test_fic_labelling_recall(self, evaluation_data):
        scenario, output = evaluation_data["fic_labelling_general"]
        result = _run_matching(scenario, output)
        assert result.recall >= 0.40, (
            f"FIC labelling recall {result.recall:.2f} < 0.40"
        )

    def test_food_supplements_precision(self, evaluation_data):
        scenario, output = evaluation_data["food_supplement_vitamin_d"]
        result = _run_matching(scenario, output)
        print("\n" + format_scenario_report(scenario.scenario_id, result))
        assert result.precision >= 0.30, (
            f"Food supplements precision {result.precision:.2f} < 0.30"
        )

    def test_food_supplements_recall(self, evaluation_data):
        scenario, output = evaluation_data["food_supplement_vitamin_d"]
        result = _run_matching(scenario, output)
        assert result.recall >= 0.40, (
            f"Food supplements recall {result.recall:.2f} < 0.40"
        )

    def test_aggregate_precision(self, evaluation_data):
        """Macro-averaged precision across all scenarios."""
        results = []
        for scenario_id, (scenario, output) in evaluation_data.items():
            result = _run_matching(scenario, output)
            results.append((scenario_id, result))

        agg = compute_aggregate_metrics(results)
        print(f"\nAggregate: P={agg['precision']:.2f} R={agg['recall']:.2f} F1={agg['f1']:.2f}")
        assert agg["precision"] >= 0.35, (
            f"Aggregate precision {agg['precision']:.2f} < 0.35"
        )

    def test_aggregate_recall(self, evaluation_data):
        """Macro-averaged recall across all scenarios."""
        results = []
        for scenario_id, (scenario, output) in evaluation_data.items():
            result = _run_matching(scenario, output)
            results.append((scenario_id, result))

        agg = compute_aggregate_metrics(results)
        assert agg["recall"] >= 0.45, (
            f"Aggregate recall {agg['recall']:.2f} < 0.45"
        )

    def test_no_hallucinated_regulations(self, evaluation_data):
        """Extracted requirements should not reference regulations outside the routed set."""
        hallucinations = []
        for scenario_id, (scenario, output) in evaluation_data.items():
            routed_ids = set(output["routing"]["celex_ids"])
            extracted = output.get("extraction", {}).get("requirements", [])
            for req in extracted:
                if req["regulation_id"] not in routed_ids:
                    hallucinations.append(
                        f"{scenario_id}: {req['regulation_id']} Art {req['article_number']}"
                    )

        assert not hallucinations, (
            f"Found {len(hallucinations)} hallucinated regulation references:\n"
            + "\n".join(f"  - {h}" for h in hallucinations)
        )

    def test_no_entity_extraction_gaps(self, evaluation_data):
        """All ground truth regulations should be in the routed set."""
        from src.evaluation.failure_analysis import (
            ErrorCategory,
            classify_false_negative,
        )

        gaps = []
        for scenario_id, (scenario, output) in evaluation_data.items():
            result = _run_matching(scenario, output)
            for fn in result.false_negatives:
                diag = classify_false_negative(fn, output)
                if diag.error_category == ErrorCategory.ENTITY_EXTRACTION_GAP:
                    gaps.append(
                        f"{scenario_id}: {fn.regulation_id} Art {fn.article_number}"
                    )

        assert not gaps, (
            f"Found {len(gaps)} entity extraction gaps:\n"
            + "\n".join(f"  - {g}" for g in gaps)
        )

    def test_failure_analysis_report(self, evaluation_data):
        """Run full failure analysis and print the report (always passes)."""
        from src.evaluation.failure_analysis import (
            analyze_scenario,
            format_failure_report,
            AggregateFailureAnalysis,
        )

        agg = AggregateFailureAnalysis()
        for scenario_id, (scenario, output) in sorted(evaluation_data.items()):
            result = _run_matching(scenario, output)
            analysis = analyze_scenario(
                scenario_id, result, output, scenario.product_type
            )
            agg.scenarios.append(analysis)

        print("\n" + format_failure_report(agg))

    def test_full_diagnostic_report(self, evaluation_data):
        """Print full diagnostic report for all scenarios (always passes)."""
        results = []
        print("\n" + "=" * 60)
        for scenario_id, (scenario, output) in sorted(evaluation_data.items()):
            result = _run_matching(scenario, output)
            results.append((scenario_id, result))
            print(format_scenario_report(scenario_id, result))

        agg = compute_aggregate_metrics(results)
        print("=" * 60)
        print(f"AGGREGATE ({agg['scenarios']} scenarios)")
        print(f"  Precision: {agg['precision']:.2f}")
        print(f"  Recall:    {agg['recall']:.2f}")
        print(f"  F1:        {agg['f1']:.2f}")
        print("=" * 60)
