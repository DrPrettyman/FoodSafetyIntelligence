"""
Data structures for extraction evaluation.

Defines ground truth checklists, evaluation scenarios, and match results
for computing precision/recall of LLM-extracted compliance requirements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GroundTruthRequirement:
    """A single expected compliance requirement in a ground truth checklist."""

    requirement_id: str  # unique within scenario, e.g. "NF-01"
    regulation_id: str  # CELEX number, e.g. "32015R2283"
    article_number: int  # primary article
    requirement_type: str  # RequirementType value, e.g. "authorisation"
    description: str  # human-readable description
    priority: str  # Priority value, e.g. "before_launch"
    source: str  # provenance, e.g. "Regulation (EU) 2015/2283 Art 6(2)"
    notes: str = ""  # matching caveats


@dataclass
class EvaluationScenario:
    """A complete evaluation scenario: pipeline inputs + expected outputs."""

    scenario_id: str
    description: str
    # Pipeline input parameters
    product_type: str = ""
    ingredients: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    packaging: str = ""
    keywords: list[str] = field(default_factory=list)
    query_text: str = ""
    n_results: int = 10
    # Ground truth
    requirements: list[GroundTruthRequirement] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: Path) -> EvaluationScenario:
        """Load a scenario from a JSON file."""
        with open(path) as f:
            data = json.load(f)

        inputs = data.get("pipeline_inputs", {})
        gt_reqs = [
            GroundTruthRequirement(**r)
            for r in data.get("ground_truth_requirements", [])
        ]

        return cls(
            scenario_id=data["scenario_id"],
            description=data["description"],
            product_type=inputs.get("product_type", ""),
            ingredients=inputs.get("ingredients", []),
            claims=inputs.get("claims", []),
            packaging=inputs.get("packaging", ""),
            keywords=inputs.get("keywords", []),
            query_text=inputs.get("query_text", ""),
            n_results=inputs.get("n_results", 10),
            requirements=gt_reqs,
        )


@dataclass
class MatchResult:
    """Result of matching extracted requirements against ground truth."""

    true_positives: list[tuple[GroundTruthRequirement, dict]] = field(
        default_factory=list
    )
    partial_matches: list[tuple[GroundTruthRequirement, dict, str]] = field(
        default_factory=list
    )
    false_positives: list[dict] = field(default_factory=list)
    false_negatives: list[GroundTruthRequirement] = field(default_factory=list)

    @property
    def precision(self) -> float:
        tp = len(self.true_positives) + len(self.partial_matches)
        total = tp + len(self.false_positives)
        return tp / total if total > 0 else 0.0

    @property
    def recall(self) -> float:
        tp = len(self.true_positives) + len(self.partial_matches)
        total = tp + len(self.false_negatives)
        return tp / total if total > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0
