"""
Matching engine for comparing extracted requirements against ground truth.

Uses key-based matching (regulation_id, article_number, requirement_type) with
a relaxed fallback for partial matches where the requirement type differs but
the content overlaps.
"""

from __future__ import annotations

from src.evaluation.schemas import GroundTruthRequirement, MatchResult

# Words to ignore when computing description overlap
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "shall", "should", "may", "might", "can", "could", "must",
    "not", "no", "nor", "it", "its", "this", "that", "these", "those",
    "all", "each", "every", "any", "which", "who", "whom", "what",
    "their", "they", "them", "such", "than", "other",
})


def _match_key(req: dict | GroundTruthRequirement) -> tuple[str, int, str]:
    """Create a matching key from a requirement (extracted dict or ground truth)."""
    if isinstance(req, GroundTruthRequirement):
        return (req.regulation_id, req.article_number, req.requirement_type)
    return (req["regulation_id"], req["article_number"], req["requirement_type"])


def _significant_words(text: str) -> set[str]:
    """Extract significant words from text (lowered, stopwords removed)."""
    words = set(text.lower().split())
    return words - _STOPWORDS


def _word_overlap(text_a: str, text_b: str) -> int:
    """Count shared significant words between two texts."""
    return len(_significant_words(text_a) & _significant_words(text_b))


def _is_partial_match(
    extracted: dict,
    gt: GroundTruthRequirement,
    min_word_overlap: int = 3,
) -> tuple[bool, str]:
    """Check if an extracted requirement partially matches a ground truth item.

    A partial match requires 2 of 3 key fields to match AND sufficient
    word overlap between descriptions.

    Returns:
        (is_match, reason) tuple.
    """
    matches = 0
    mismatches = []

    if extracted["regulation_id"] == gt.regulation_id:
        matches += 1
    else:
        mismatches.append("regulation_id")

    if extracted["article_number"] == gt.article_number:
        matches += 1
    else:
        mismatches.append("article_number")

    if extracted["requirement_type"] == gt.requirement_type:
        matches += 1
    else:
        mismatches.append("requirement_type")

    if matches < 2:
        return False, ""

    # Check description overlap
    extracted_text = extracted.get("requirement_summary", "")
    overlap = _word_overlap(extracted_text, gt.description)

    if overlap >= min_word_overlap:
        reason = f"partial: {', '.join(mismatches)} mismatch, {overlap} words overlap"
        return True, reason

    return False, ""


def match_requirements(
    extracted: list[dict],
    ground_truth: list[GroundTruthRequirement],
    allow_partial: bool = True,
) -> MatchResult:
    """Match extracted requirements against ground truth.

    Algorithm:
    1. Build key index of ground truth items.
    2. For each extracted requirement, try exact key match first.
    3. If no exact match and allow_partial, try relaxed matching.
    4. Remaining extracted → false positives.
    5. Remaining unmatched ground truth → false negatives.

    One-to-one matching: each ground truth item matches at most one extraction.
    """
    result = MatchResult()

    # Track which ground truth items have been matched
    unmatched_gt = {gt.requirement_id: gt for gt in ground_truth}

    # Build ground truth key index (key -> requirement_id)
    gt_by_key: dict[tuple[str, int, str], str] = {}
    for gt in ground_truth:
        key = _match_key(gt)
        gt_by_key[key] = gt.requirement_id

    # Phase 1: Exact matches
    unmatched_extracted = []
    for ext in extracted:
        key = _match_key(ext)
        if key in gt_by_key:
            gt_id = gt_by_key[key]
            if gt_id in unmatched_gt:
                gt_item = unmatched_gt.pop(gt_id)
                result.true_positives.append((gt_item, ext))
                # Remove key so duplicate extractions become FP
                del gt_by_key[key]
                continue
        unmatched_extracted.append(ext)

    # Phase 2: Relaxed matches
    if allow_partial:
        still_unmatched = []
        for ext in unmatched_extracted:
            matched = False
            for gt_id, gt_item in list(unmatched_gt.items()):
                is_match, reason = _is_partial_match(ext, gt_item)
                if is_match:
                    result.partial_matches.append((gt_item, ext, reason))
                    del unmatched_gt[gt_id]
                    matched = True
                    break
            if not matched:
                still_unmatched.append(ext)
        unmatched_extracted = still_unmatched

    # Remaining
    result.false_positives = unmatched_extracted
    result.false_negatives = list(unmatched_gt.values())

    return result
