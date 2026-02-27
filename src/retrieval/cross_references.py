"""
Cross-reference resolution: expand routed regulation sets by following
inter-regulation references.

The entity extractor captures cross-references like "Regulation (EC) No 178/2002"
with human-readable target numbers. This module resolves those to CELEX IDs and
provides 1-hop expansion for the pipeline's query phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.extraction.entity_extractor import CrossReference


def regulation_number_to_celex(
    number_str: str,
    corpus_celex_ids: set[str],
) -> str | None:
    """Map a human-readable regulation number to a CELEX ID.

    Tries both interpretations against the known corpus:
    - Old-style (EC): '178/2002' → number=178, year=2002 → 32002R0178
    - New-style (EU): '2015/2283' → year=2015, number=2283 → 32015R2283
    - Also tries L (Directive) prefix variants

    Returns the first match found in the corpus, or None if unresolvable.
    """
    parts = number_str.split("/")
    if len(parts) != 2:
        return None

    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return None

    # Generate candidates: both number/year and year/number, both R and L
    candidates = [
        f"3{second}R{first:04d}",  # first/second as number/year, Regulation
        f"3{second}L{first:04d}",  # first/second as number/year, Directive
        f"3{first}R{second:04d}",  # first/second as year/number, Regulation
        f"3{first}L{second:04d}",  # first/second as year/number, Directive
    ]

    for candidate in candidates:
        if candidate in corpus_celex_ids:
            return candidate
    return None


@dataclass
class CrossReferenceIndex:
    """Precomputed cross-reference lookup for retrieval expansion.

    Built from extracted cross-references and the known corpus. Provides
    1-hop expansion: given a set of routed CELEX IDs, returns additional
    CELEX IDs referenced by those regulations.
    """

    _source_to_targets: dict[str, set[str]] = field(default_factory=dict)
    _unresolved: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        cross_references: list[CrossReference],
        corpus_celex_ids: set[str],
    ) -> CrossReferenceIndex:
        """Build from extracted cross-references and known corpus CELEX IDs."""
        source_to_targets: dict[str, set[str]] = {}
        unresolved: dict[str, set[str]] = {}

        for ref in cross_references:
            target_celex = regulation_number_to_celex(
                ref.target_regulation_number, corpus_celex_ids
            )

            if target_celex and target_celex != ref.source_celex:
                source_to_targets.setdefault(ref.source_celex, set()).add(
                    target_celex
                )
            elif not target_celex:
                unresolved.setdefault(ref.source_celex, set()).add(
                    ref.target_regulation_number
                )

        return cls(
            _source_to_targets=source_to_targets,
            _unresolved=unresolved,
        )

    def expand(
        self, celex_ids: list[str]
    ) -> tuple[list[str], dict[str, list[str]]]:
        """Expand a set of CELEX IDs with cross-referenced regulations.

        Returns:
            (new_celex_ids, reasons) where reasons maps each added CELEX ID
            to a list of explanation strings.
        """
        existing = set(celex_ids)
        new_ids: list[str] = []
        reasons: dict[str, list[str]] = {}

        for source_celex in celex_ids:
            targets = self._source_to_targets.get(source_celex, set())
            for target in targets:
                if target not in existing:
                    existing.add(target)
                    new_ids.append(target)
                    reasons[target] = []
                if target in reasons:
                    reasons[target].append(
                        f"cross-referenced from {source_celex}"
                    )

        return new_ids, reasons

    @property
    def resolved_count(self) -> int:
        """Total number of resolved cross-reference links."""
        return sum(len(targets) for targets in self._source_to_targets.values())

    @property
    def unresolved_count(self) -> int:
        """Total number of unresolved target regulation numbers."""
        return sum(len(targets) for targets in self._unresolved.values())
