"""
Run failure mode analysis on cached evaluation results.

Loads ground truth + most recent cached extraction per scenario,
runs matching + failure classification, and outputs a report.

Usage:
    python scripts/run_failure_analysis.py
    python scripts/run_failure_analysis.py --output data/evaluation/failure_analysis
"""

import argparse
import json
from pathlib import Path

from src.evaluation.failure_analysis import (
    analyze_all,
    analyze_scenario,
    format_failure_report,
    save_failure_analysis,
)
from src.evaluation.matching import match_requirements
from src.evaluation.schemas import EvaluationScenario

GT_DIR = Path("data/evaluation/ground_truth")
CACHE_DIR = Path("data/evaluation/cache")
DEFAULT_OUTPUT = Path("data/evaluation/failure_analysis")


def _load_evaluation_data() -> dict[str, tuple[EvaluationScenario, dict]]:
    """Load ground truth and most recent cached results for each scenario."""
    data = {}

    for gt_path in sorted(GT_DIR.glob("scenario_*.json")):
        scenario = EvaluationScenario.from_json(gt_path)

        cache_files = sorted(CACHE_DIR.glob(f"{scenario.scenario_id}_run_*.json"))
        if not cache_files:
            print(f"  No cache for {scenario.scenario_id}, skipping")
            continue

        with open(cache_files[-1]) as f:
            cache_entry = json.load(f)

        data[scenario.scenario_id] = (scenario, cache_entry["pipeline_output"])
        print(f"  Loaded {scenario.scenario_id} ({cache_files[-1].name})")

    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run failure mode analysis")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    print("Loading evaluation data...")
    evaluation_data = _load_evaluation_data()

    if not evaluation_data:
        print("No evaluation data found. Run extraction scenarios first:")
        print("  python scripts/run_extraction_scenarios.py --provider claude-code")
        return

    print(f"\nRunning failure analysis on {len(evaluation_data)} scenarios...")

    # Run matching and collect results
    match_results = {}
    for scenario_id, (scenario, output) in evaluation_data.items():
        extracted = output.get("extraction", {}).get("requirements", [])
        match_results[scenario_id] = match_requirements(
            extracted, scenario.requirements
        )

    # Run failure analysis
    agg = analyze_all(evaluation_data, match_results)

    # Print report
    report = format_failure_report(agg)
    print("\n" + report)

    # Save outputs
    json_path, md_path = save_failure_analysis(agg, args.output)
    print(f"\nSaved JSON:     {json_path}")
    print(f"Saved Markdown: {md_path}")


if __name__ == "__main__":
    main()
