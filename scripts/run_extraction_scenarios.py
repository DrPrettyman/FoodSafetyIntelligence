"""
Populate the evaluation cache by running the pipeline on each ground truth scenario.

Usage:
    python scripts/run_extraction_scenarios.py --provider claude-code
    python scripts/run_extraction_scenarios.py --provider anthropic --scenario novel_food_insect_protein
"""

import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

GT_DIR = Path("data/evaluation/ground_truth")
CACHE_DIR = Path("data/evaluation/cache")


def run_scenario(scenario_path: Path, provider: str, model: str | None) -> dict:
    """Run a single scenario through the pipeline and return the cache entry."""
    from src.pipeline import query

    with open(scenario_path) as f:
        scenario = json.load(f)

    inputs = scenario["pipeline_inputs"]
    scenario_id = scenario["scenario_id"]

    print(f"\nRunning scenario: {scenario_id}")
    print(f"  Product type: {inputs.get('product_type', '(none)')}")
    print(f"  Query: {inputs.get('query_text', '(auto)')}")
    print(f"  Provider: {provider}")

    pipeline_output = query(
        product_type=inputs.get("product_type", ""),
        ingredients=inputs.get("ingredients"),
        claims=inputs.get("claims"),
        packaging=inputs.get("packaging", ""),
        keywords=inputs.get("keywords"),
        query_text=inputs.get("query_text", ""),
        n_results=inputs.get("n_results", 10),
        provider=provider,
        model=model,
    )

    # Count run number
    existing = list(CACHE_DIR.glob(f"{scenario_id}_run_*.json"))
    run_num = len(existing) + 1

    cache_entry = {
        "scenario_id": scenario_id,
        "run_id": f"run_{run_num:03d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "pipeline_output": pipeline_output,
    }

    return cache_entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Run extraction scenarios for evaluation")
    parser.add_argument(
        "--provider", default="claude-code",
        choices=["anthropic", "openai", "claude-code"],
        help="LLM provider (default: claude-code)",
    )
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument(
        "--scenario", default=None,
        help="Run a specific scenario ID (default: all)",
    )
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    scenario_files = sorted(GT_DIR.glob("scenario_*.json"))
    if not scenario_files:
        print(f"No ground truth files found in {GT_DIR}")
        return

    if args.scenario:
        scenario_files = [
            f for f in scenario_files
            if args.scenario in f.stem
        ]
        if not scenario_files:
            print(f"No matching scenario for '{args.scenario}'")
            return

    print(f"Found {len(scenario_files)} scenario(s) to run")

    for scenario_path in scenario_files:
        try:
            cache_entry = run_scenario(scenario_path, args.provider, args.model)

            scenario_id = cache_entry["scenario_id"]
            run_id = cache_entry["run_id"]
            cache_path = CACHE_DIR / f"{scenario_id}_{run_id}.json"

            with open(cache_path, "w") as f:
                json.dump(cache_entry, f, indent=2, default=str)

            extraction = cache_entry["pipeline_output"].get("extraction", {})
            n_reqs = extraction.get("requirements_count", 0)
            print(f"  Extracted {n_reqs} requirements → {cache_path}")

        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
