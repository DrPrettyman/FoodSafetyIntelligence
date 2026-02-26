"""
Metric computation and reporting for extraction evaluation.
"""

from __future__ import annotations

from src.evaluation.schemas import MatchResult


def compute_scenario_metrics(scenario_id: str, result: MatchResult) -> dict:
    """Compute metrics for a single scenario."""
    return {
        "scenario_id": scenario_id,
        "precision": round(result.precision, 3),
        "recall": round(result.recall, 3),
        "f1": round(result.f1, 3),
        "true_positives": len(result.true_positives),
        "partial_matches": len(result.partial_matches),
        "false_positives": len(result.false_positives),
        "false_negatives": len(result.false_negatives),
        "additional_detail": len(result.additional_detail),
    }


def compute_aggregate_metrics(
    scenario_results: list[tuple[str, MatchResult]],
) -> dict:
    """Compute macro-averaged metrics across all scenarios."""
    if not scenario_results:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "scenarios": 0}

    precisions = [r.precision for _, r in scenario_results]
    recalls = [r.recall for _, r in scenario_results]
    f1s = [r.f1 for _, r in scenario_results]
    n = len(scenario_results)

    avg_p = sum(precisions) / n
    avg_r = sum(recalls) / n
    avg_f1 = sum(f1s) / n

    return {
        "precision": round(avg_p, 3),
        "recall": round(avg_r, 3),
        "f1": round(avg_f1, 3),
        "scenarios": n,
        "per_scenario": [
            compute_scenario_metrics(sid, r) for sid, r in scenario_results
        ],
    }


def format_scenario_report(scenario_id: str, result: MatchResult) -> str:
    """Format a human-readable report for a single scenario."""
    lines = [
        f"=== SCENARIO: {scenario_id} ===",
        f"Precision: {result.precision:.2f}  "
        f"Recall: {result.recall:.2f}  "
        f"F1: {result.f1:.2f}",
        "",
    ]

    if result.true_positives:
        lines.append(f"TRUE POSITIVES ({len(result.true_positives)}):")
        for gt, ext in result.true_positives:
            lines.append(
                f"  {gt.requirement_id} [{gt.regulation_id} Art {gt.article_number} "
                f"{gt.requirement_type}]"
            )
        lines.append("")

    if result.partial_matches:
        lines.append(f"PARTIAL MATCHES ({len(result.partial_matches)}):")
        for gt, ext, reason in result.partial_matches:
            lines.append(
                f"  {gt.requirement_id} [{gt.regulation_id} Art {gt.article_number}] "
                f"— {reason}"
            )
        lines.append("")

    if result.false_positives:
        lines.append(f"FALSE POSITIVES ({len(result.false_positives)}):")
        for ext in result.false_positives:
            lines.append(
                f"  [{ext['regulation_id']} Art {ext['article_number']} "
                f"{ext['requirement_type']}] — {ext.get('requirement_summary', '')[:80]}"
            )
        lines.append("")

    if result.false_negatives:
        lines.append(f"FALSE NEGATIVES ({len(result.false_negatives)}):")
        for gt in result.false_negatives:
            lines.append(
                f"  {gt.requirement_id} [{gt.regulation_id} Art {gt.article_number} "
                f"{gt.requirement_type}] — {gt.description[:80]}"
            )
        lines.append("")

    if result.additional_detail:
        lines.append(f"ADDITIONAL DETAIL ({len(result.additional_detail)}) — "
                      "extra sub-requirements from matched articles, not counted as FP:")
        for ext in result.additional_detail:
            lines.append(
                f"  [{ext['regulation_id']} Art {ext['article_number']} "
                f"{ext['requirement_type']}] — {ext.get('requirement_summary', '')[:80]}"
            )
        lines.append("")

    return "\n".join(lines)
