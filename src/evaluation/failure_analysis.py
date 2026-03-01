"""
Failure mode analysis for the EU Food Safety Regulatory Intelligence Engine.

Classifies every false positive and false negative from evaluation matching
into specific error categories to identify where the pipeline fails and why.

Error categories (from comprehensivePlan.md Section 7, Layer 4):
  FN categories:
    1. entity_extraction_gap — regulated entity not in index
    2. routing_miss — input should have triggered a regulation but didn't
    3. retrieval_failure — regulation routed but article not retrieved
    4. extraction_failure — article retrieved but requirement not extracted
    5. cross_reference_miss — regulation referenced but not resolved

  FP categories:
    1. tangential_cross_ref — valid extraction from cross-ref-expanded regulation
    2. scope_error — requirement applies to different product domain
    3. over_extraction — valid but generic / not in ground truth
    4. hallucination — regulation not in routed set or no source text
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from src.evaluation.schemas import GroundTruthRequirement, MatchResult


class ErrorCategory(str, Enum):
    """FN error categories — identifies the pipeline stage that failed."""

    ENTITY_EXTRACTION_GAP = "entity_extraction_gap"
    ROUTING_MISS = "routing_miss"
    RETRIEVAL_FAILURE = "retrieval_failure"
    EXTRACTION_FAILURE = "extraction_failure"
    CROSS_REFERENCE_MISS = "cross_reference_miss"


class FPCategory(str, Enum):
    """FP sub-classification — explains why a false positive occurred."""

    TANGENTIAL_CROSS_REF = "tangential_cross_ref"
    SCOPE_ERROR = "scope_error"
    OVER_EXTRACTION = "over_extraction"
    HALLUCINATION = "hallucination"


@dataclass
class FNDiagnosis:
    """Diagnosis for a single false negative."""

    ground_truth: GroundTruthRequirement
    error_category: ErrorCategory
    was_routed: bool
    was_retrieved: bool
    explanation: str


@dataclass
class FPDiagnosis:
    """Diagnosis for a single false positive."""

    extracted: dict
    fp_category: FPCategory
    is_cross_ref_expansion: bool
    confidence: float
    explanation: str


@dataclass
class ScenarioFailureAnalysis:
    """Complete failure analysis for one scenario."""

    scenario_id: str
    fn_diagnoses: list[FNDiagnosis] = field(default_factory=list)
    fp_diagnoses: list[FPDiagnosis] = field(default_factory=list)

    @property
    def fn_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {cat.value: 0 for cat in ErrorCategory}
        for diag in self.fn_diagnoses:
            counts[diag.error_category.value] += 1
        return counts

    @property
    def fp_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {cat.value: 0 for cat in FPCategory}
        for diag in self.fp_diagnoses:
            counts[diag.fp_category.value] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "fn_count": len(self.fn_diagnoses),
            "fp_count": len(self.fp_diagnoses),
            "fn_by_category": self.fn_by_category,
            "fp_by_category": self.fp_by_category,
            "fn_details": [
                {
                    "requirement_id": d.ground_truth.requirement_id,
                    "regulation_id": d.ground_truth.regulation_id,
                    "article_number": d.ground_truth.article_number,
                    "requirement_type": d.ground_truth.requirement_type,
                    "error_category": d.error_category.value,
                    "was_routed": d.was_routed,
                    "was_retrieved": d.was_retrieved,
                    "explanation": d.explanation,
                }
                for d in self.fn_diagnoses
            ],
            "fp_details": [
                {
                    "regulation_id": d.extracted.get("regulation_id", ""),
                    "article_number": d.extracted.get("article_number", 0),
                    "requirement_type": d.extracted.get("requirement_type", ""),
                    "fp_category": d.fp_category.value,
                    "is_cross_ref_expansion": d.is_cross_ref_expansion,
                    "confidence": d.confidence,
                    "explanation": d.explanation,
                }
                for d in self.fp_diagnoses
            ],
        }


@dataclass
class AggregateFailureAnalysis:
    """Aggregate failure analysis across all scenarios."""

    scenarios: list[ScenarioFailureAnalysis] = field(default_factory=list)

    @property
    def total_fn_by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {cat.value: 0 for cat in ErrorCategory}
        for scenario in self.scenarios:
            for cat, count in scenario.fn_by_category.items():
                totals[cat] += count
        return totals

    @property
    def total_fp_by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {cat.value: 0 for cat in FPCategory}
        for scenario in self.scenarios:
            for cat, count in scenario.fp_by_category.items():
                totals[cat] += count
        return totals

    @property
    def total_fn(self) -> int:
        return sum(len(s.fn_diagnoses) for s in self.scenarios)

    @property
    def total_fp(self) -> int:
        return sum(len(s.fp_diagnoses) for s in self.scenarios)

    def to_dict(self) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario_count": len(self.scenarios),
            "summary": {
                "total_fn": self.total_fn,
                "total_fp": self.total_fp,
                "fn_by_category": self.total_fn_by_category,
                "fp_by_category": self.total_fp_by_category,
            },
            "per_scenario": {
                s.scenario_id: s.to_dict() for s in self.scenarios
            },
        }


# ---------------------------------------------------------------------------
# Classification functions
# ---------------------------------------------------------------------------


def classify_false_negative(
    fn: GroundTruthRequirement,
    pipeline_output: dict,
) -> FNDiagnosis:
    """Trace a false negative through the pipeline to identify failure stage.

    Checks routing → retrieval → extraction in order.
    """
    routing = pipeline_output.get("routing", {})
    retrieval = pipeline_output.get("retrieval", {})
    extraction = pipeline_output.get("extraction", {})

    routed_celex = set(routing.get("celex_ids", []))
    was_routed = fn.regulation_id in routed_celex

    if not was_routed:
        # Check if it was a cross-reference that couldn't be resolved
        xref = routing.get("cross_references", {})
        expanded = set(xref.get("expanded_celex_ids", []))
        if fn.regulation_id in expanded:
            # It was expanded but still not in the final set — shouldn't happen
            # but handle gracefully
            return FNDiagnosis(
                ground_truth=fn,
                error_category=ErrorCategory.ROUTING_MISS,
                was_routed=False,
                was_retrieved=False,
                explanation=(
                    f"{fn.regulation_id} was cross-reference expanded but "
                    f"not in final routed set"
                ),
            )
        # Not routed at all
        return FNDiagnosis(
            ground_truth=fn,
            error_category=ErrorCategory.ROUTING_MISS,
            was_routed=False,
            was_retrieved=False,
            explanation=(
                f"{fn.regulation_id} not in routed set "
                f"({len(routed_celex)} regulations routed)"
            ),
        )

    # Regulation was routed — check if the specific article was retrieved
    retrieved_articles = retrieval.get("articles", [])
    article_retrieved = any(
        a.get("metadata", {}).get("celex_id") == fn.regulation_id
        and a.get("metadata", {}).get("article_number") == fn.article_number
        for a in retrieved_articles
    )

    if not article_retrieved:
        # Check if ANY article from this regulation was retrieved
        reg_articles = [
            a for a in retrieved_articles
            if a.get("metadata", {}).get("celex_id") == fn.regulation_id
        ]
        if reg_articles:
            retrieved_art_nums = sorted(set(
                a["metadata"]["article_number"] for a in reg_articles
            ))
            explanation = (
                f"{fn.regulation_id} Art {fn.article_number} not in "
                f"retrieved articles; regulation has Arts "
                f"{retrieved_art_nums} retrieved"
            )
        else:
            explanation = (
                f"{fn.regulation_id} routed but no articles retrieved "
                f"by vector search"
            )
        return FNDiagnosis(
            ground_truth=fn,
            error_category=ErrorCategory.RETRIEVAL_FAILURE,
            was_routed=True,
            was_retrieved=False,
            explanation=explanation,
        )

    # Article was retrieved — check if it was extracted
    extracted_reqs = extraction.get("requirements", [])
    article_extracted = any(
        r.get("regulation_id") == fn.regulation_id
        and r.get("article_number") == fn.article_number
        for r in extracted_reqs
    )

    if not article_extracted:
        # Check if ANY extraction from this regulation
        reg_extractions = [
            r for r in extracted_reqs
            if r.get("regulation_id") == fn.regulation_id
        ]
        if reg_extractions:
            extracted_art_nums = sorted(set(
                r["article_number"] for r in reg_extractions
            ))
            explanation = (
                f"{fn.regulation_id} Art {fn.article_number} retrieved but "
                f"not extracted; LLM extracted Arts {extracted_art_nums}"
            )
        else:
            explanation = (
                f"{fn.regulation_id} Art {fn.article_number} retrieved but "
                f"LLM extracted nothing from this regulation"
            )
        return FNDiagnosis(
            ground_truth=fn,
            error_category=ErrorCategory.EXTRACTION_FAILURE,
            was_routed=True,
            was_retrieved=True,
            explanation=explanation,
        )

    # Article was retrieved AND something was extracted from it,
    # but the matching engine didn't match it. This means the
    # requirement_type or description didn't overlap enough.
    return FNDiagnosis(
        ground_truth=fn,
        error_category=ErrorCategory.EXTRACTION_FAILURE,
        was_routed=True,
        was_retrieved=True,
        explanation=(
            f"{fn.regulation_id} Art {fn.article_number} retrieved and "
            f"extracted, but matching failed — likely requirement_type "
            f"mismatch (expected '{fn.requirement_type}')"
        ),
    )


def classify_false_positive(
    fp: dict,
    pipeline_output: dict,
    scenario_product_type: str = "",
) -> FPDiagnosis:
    """Classify a false positive extraction into a sub-category."""
    routing = pipeline_output.get("routing", {})
    routed_celex = set(routing.get("celex_ids", []))
    reasons = routing.get("reasons", {})
    reg_id = fp.get("regulation_id", "")
    confidence = fp.get("confidence", 0.0)

    # Check if regulation is in the routed set
    if reg_id not in routed_celex:
        return FPDiagnosis(
            extracted=fp,
            fp_category=FPCategory.HALLUCINATION,
            is_cross_ref_expansion=False,
            confidence=confidence,
            explanation=(
                f"{reg_id} not in routed set — requirement references "
                f"unrouted regulation"
            ),
        )

    # Check if from cross-reference expansion
    reg_reasons = reasons.get(reg_id, [])
    is_cross_ref = any("cross-referenced from" in r for r in reg_reasons)

    if is_cross_ref:
        source_regs = [
            r.split("cross-referenced from ")[-1]
            for r in reg_reasons
            if "cross-referenced from" in r
        ]
        return FPDiagnosis(
            extracted=fp,
            fp_category=FPCategory.TANGENTIAL_CROSS_REF,
            is_cross_ref_expansion=True,
            confidence=confidence,
            explanation=(
                f"{reg_id} Art {fp.get('article_number', '?')} added via "
                f"cross-reference from {', '.join(source_regs)} — "
                f"valid extraction but tangential to scenario"
            ),
        )

    # Check for scope error — applicable_to or conditions suggest
    # a different product domain
    applicable_to = fp.get("applicable_to", "").lower()
    conditions = fp.get("conditions", "").lower()
    combined_context = f"{applicable_to} {conditions}"

    # Domain mismatch keywords by scenario product type
    _DOMAIN_MISMATCHES: dict[str, list[str]] = {
        "novel food": [
            "gmo", "genetically modified", "animal origin", "enzyme",
            "feed", "organic", "infant formula",
        ],
        "food supplement": [
            "gmo", "genetically modified", "animal origin", "enzyme",
            "feed", "organic", "infant formula", "novel food",
        ],
        "": [
            "gmo", "genetically modified", "animal origin", "enzyme",
            "feed",
        ],
    }
    mismatch_terms = _DOMAIN_MISMATCHES.get(
        scenario_product_type.lower(),
        _DOMAIN_MISMATCHES[""],
    )

    for term in mismatch_terms:
        if term in combined_context:
            return FPDiagnosis(
                extracted=fp,
                fp_category=FPCategory.SCOPE_ERROR,
                is_cross_ref_expansion=False,
                confidence=confidence,
                explanation=(
                    f"{reg_id} Art {fp.get('article_number', '?')}: "
                    f"applicable_to/conditions mention '{term}' — "
                    f"scope mismatch for '{scenario_product_type}' scenario"
                ),
            )

    # Default: over-extraction (valid requirement, just not in ground truth)
    return FPDiagnosis(
        extracted=fp,
        fp_category=FPCategory.OVER_EXTRACTION,
        is_cross_ref_expansion=False,
        confidence=confidence,
        explanation=(
            f"{reg_id} Art {fp.get('article_number', '?')} "
            f"{fp.get('requirement_type', '')}: valid extraction not "
            f"covered by ground truth (conf={confidence:.2f})"
        ),
    )


# ---------------------------------------------------------------------------
# Scenario and aggregate analysis
# ---------------------------------------------------------------------------


def analyze_scenario(
    scenario_id: str,
    match_result: MatchResult,
    pipeline_output: dict,
    scenario_product_type: str = "",
) -> ScenarioFailureAnalysis:
    """Run full failure analysis for a single scenario."""
    analysis = ScenarioFailureAnalysis(scenario_id=scenario_id)

    for fn in match_result.false_negatives:
        analysis.fn_diagnoses.append(
            classify_false_negative(fn, pipeline_output)
        )

    for fp in match_result.false_positives:
        analysis.fp_diagnoses.append(
            classify_false_positive(fp, pipeline_output, scenario_product_type)
        )

    return analysis


def analyze_all(
    evaluation_data: dict[str, tuple],
    match_results: dict[str, MatchResult],
) -> AggregateFailureAnalysis:
    """Run failure analysis across all scenarios."""
    agg = AggregateFailureAnalysis()

    for scenario_id in sorted(evaluation_data.keys()):
        scenario, output = evaluation_data[scenario_id]
        result = match_results[scenario_id]
        analysis = analyze_scenario(
            scenario_id, result, output, scenario.product_type
        )
        agg.scenarios.append(analysis)

    return agg


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_failure_report(analysis: AggregateFailureAnalysis) -> str:
    """Generate a human-readable markdown report."""
    lines: list[str] = []

    lines.append("# Failure Mode Analysis Report")
    lines.append("")
    lines.append(f"**{len(analysis.scenarios)} scenarios** | "
                 f"**{analysis.total_fn} false negatives** | "
                 f"**{analysis.total_fp} false positives**")
    lines.append("")

    # --- FN distribution ---
    lines.append("## False Negative Distribution")
    lines.append("")
    lines.append("| Category | Count | % | Description |")
    lines.append("|----------|-------|---|-------------|")
    fn_cats = analysis.total_fn_by_category
    for cat in ErrorCategory:
        count = fn_cats[cat.value]
        pct = (count / analysis.total_fn * 100) if analysis.total_fn > 0 else 0
        desc = {
            ErrorCategory.ENTITY_EXTRACTION_GAP: "Entity not in index, can't route",
            ErrorCategory.ROUTING_MISS: "Input should trigger regulation but didn't",
            ErrorCategory.RETRIEVAL_FAILURE: "Regulation routed, article not retrieved",
            ErrorCategory.EXTRACTION_FAILURE: "Article retrieved, requirement not extracted",
            ErrorCategory.CROSS_REFERENCE_MISS: "Referenced regulation not resolved",
        }[cat]
        lines.append(f"| {cat.value} | {count} | {pct:.0f}% | {desc} |")
    lines.append("")

    # --- FP distribution ---
    lines.append("## False Positive Distribution")
    lines.append("")
    lines.append("| Category | Count | % | Description |")
    lines.append("|----------|-------|---|-------------|")
    fp_cats = analysis.total_fp_by_category
    for cat in FPCategory:
        count = fp_cats[cat.value]
        pct = (count / analysis.total_fp * 100) if analysis.total_fp > 0 else 0
        desc = {
            FPCategory.TANGENTIAL_CROSS_REF: "Valid from cross-ref regulation, tangential",
            FPCategory.SCOPE_ERROR: "Applies to different product domain",
            FPCategory.OVER_EXTRACTION: "Valid requirement, not in ground truth",
            FPCategory.HALLUCINATION: "References unrouted regulation",
        }[cat]
        lines.append(f"| {cat.value} | {count} | {pct:.0f}% | {desc} |")
    lines.append("")

    # --- Per-scenario detail ---
    for scenario_analysis in analysis.scenarios:
        lines.append(f"## Scenario: {scenario_analysis.scenario_id}")
        lines.append("")

        if scenario_analysis.fn_diagnoses:
            lines.append(f"### False Negatives ({len(scenario_analysis.fn_diagnoses)})")
            lines.append("")
            for diag in scenario_analysis.fn_diagnoses:
                gt = diag.ground_truth
                lines.append(
                    f"- **{gt.requirement_id}** [{gt.regulation_id} "
                    f"Art {gt.article_number} {gt.requirement_type}] "
                    f"→ **{diag.error_category.value}**"
                )
                lines.append(f"  {diag.explanation}")
            lines.append("")

        if scenario_analysis.fp_diagnoses:
            lines.append(f"### False Positives ({len(scenario_analysis.fp_diagnoses)})")
            lines.append("")
            for diag in scenario_analysis.fp_diagnoses:
                fp = diag.extracted
                lines.append(
                    f"- [{fp.get('regulation_id', '')} "
                    f"Art {fp.get('article_number', '?')} "
                    f"{fp.get('requirement_type', '')}] "
                    f"→ **{diag.fp_category.value}** "
                    f"(conf={diag.confidence:.2f})"
                )
                lines.append(f"  {diag.explanation}")
            lines.append("")

    # --- Key findings ---
    lines.append("## Key Findings")
    lines.append("")

    fn_cats = analysis.total_fn_by_category
    fp_cats = analysis.total_fp_by_category

    if fp_cats[FPCategory.HALLUCINATION.value] == 0:
        lines.append("1. **Zero hallucinations.** The system never invents "
                      "regulations or requirements outside the routed set.")

    dominant_fn = max(fn_cats, key=fn_cats.get) if analysis.total_fn > 0 else None
    if dominant_fn and analysis.total_fn > 0:
        dominant_count = fn_cats[dominant_fn]
        dominant_pct = dominant_count / analysis.total_fn * 100
        lines.append(
            f"2. **{dominant_fn} is the primary FN cause** "
            f"({dominant_count}/{analysis.total_fn}, {dominant_pct:.0f}%). "
        )

    dominant_fp = max(fp_cats, key=fp_cats.get) if analysis.total_fp > 0 else None
    if dominant_fp and analysis.total_fp > 0:
        dominant_count = fp_cats[dominant_fp]
        dominant_pct = dominant_count / analysis.total_fp * 100
        lines.append(
            f"3. **{dominant_fp} is the primary FP cause** "
            f"({dominant_count}/{analysis.total_fp}, {dominant_pct:.0f}%)."
        )

    lines.append("")
    return "\n".join(lines)


def save_failure_analysis(
    analysis: AggregateFailureAnalysis,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Save JSON and markdown report to disk. Returns (json_path, md_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "analysis.json"
    with open(json_path, "w") as f:
        json.dump(analysis.to_dict(), f, indent=2, default=str)

    md_path = output_dir / "report.md"
    with open(md_path, "w") as f:
        f.write(format_failure_report(analysis))

    return json_path, md_path
