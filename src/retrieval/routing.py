"""
Deterministic routing table: structured product parameters → applicable regulations.

Takes structured input (product category, ingredient types, claim types, etc.)
and returns a targeted list of CELEX numbers + article ranges to search.
No LLM involved — pure lookup from corpus-extracted entities and category mappings.

The routing table is built from two sources:
1. Entity index (entity_extractor.py) — defined terms → source regulations
2. Corpus categories (corpus.py) — regulatory categories → CELEX groups

Certain regulations are always included (General Food Law, FIC labelling).
"""

from dataclasses import dataclass, field

from src.extraction.entity_extractor import EntityIndex
from src.ingestion.corpus import CATEGORIES, CORPUS


# Regulations always included in any query
ALWAYS_INCLUDE = {
    "32002R0178",  # General Food Law — foundational
    "32011R1169",  # FIC (Food Information to Consumers) — labelling is always relevant
}

# Manual mapping: high-level product/ingredient categories → regulatory categories
# This supplements the entity-based routing with domain knowledge
CATEGORY_ROUTING: dict[str, list[str]] = {
    # Product categories
    "novel food": ["novel_food"],
    "food supplement": ["food_supplements"],
    "infant formula": ["food_specific_groups"],
    "food for special medical purposes": ["food_specific_groups"],
    "organic food": ["organic"],
    # Ingredient categories
    "food additive": ["food_additives"],
    "flavouring": ["flavourings"],
    "food enzyme": ["food_enzymes"],
    "gmo": ["gmo"],
    "vitamin": ["fortification", "food_supplements"],
    "mineral": ["fortification", "food_supplements"],
    # Claim types
    "health claim": ["nutrition_health_claims"],
    "nutrition claim": ["nutrition_health_claims"],
    # Packaging
    "food contact material": ["food_contact_materials"],
    "plastic packaging": ["food_contact_materials"],
    # Labelling
    "allergen": ["labelling_fic"],
    "nutrition declaration": ["labelling_fic"],
    "origin labelling": ["labelling_fic", "meat_origin"],
    # Safety
    "contaminant": ["contaminants"],
    "official control": ["official_controls"],
}


@dataclass
class RoutingResult:
    """Result of routing: which regulations to search and why."""

    celex_ids: list[str]
    reasons: dict[str, list[str]] = field(default_factory=dict)

    def add(self, celex_id: str, reason: str) -> None:
        if celex_id not in self.reasons:
            self.reasons[celex_id] = []
            self.celex_ids.append(celex_id)
        if reason not in self.reasons[celex_id]:
            self.reasons[celex_id].append(reason)


class RoutingTable:
    """Deterministic routing from product parameters to applicable regulations.

    Built from corpus categories and extracted entity index. Supports routing by:
    - Product category (e.g., "novel food", "food supplement")
    - Ingredient type (e.g., "food additive", "flavouring")
    - Specific defined terms (e.g., "traceability", "food enzyme")
    - Regulatory category (e.g., "food_additives", "gmo")
    """

    def __init__(self, entity_index: EntityIndex | None = None):
        # Category → set of CELEX IDs
        self._category_to_celex: dict[str, set[str]] = {}
        for celex_id, info in CORPUS.items():
            cat = info["category"]
            if cat not in self._category_to_celex:
                self._category_to_celex[cat] = set()
            self._category_to_celex[cat].add(celex_id)

        # Term → set of CELEX IDs (from entity index)
        self._term_to_celex: dict[str, set[str]] = {}
        if entity_index:
            for term, sources in entity_index.term_to_sources.items():
                self._term_to_celex[term] = {s.celex_id for s in sources}

    @property
    def available_categories(self) -> list[str]:
        """All routing keywords that can be used as input."""
        return sorted(CATEGORY_ROUTING.keys())

    @property
    def available_terms(self) -> list[str]:
        """All defined terms that can trigger routing."""
        return sorted(self._term_to_celex.keys())

    @property
    def regulatory_categories(self) -> list[str]:
        """All regulatory categories from the corpus."""
        return sorted(self._category_to_celex.keys())

    def route(
        self,
        product_type: str = "",
        ingredients: list[str] | None = None,
        claims: list[str] | None = None,
        packaging: str = "",
        keywords: list[str] | None = None,
    ) -> RoutingResult:
        """Route structured product parameters to applicable regulations.

        Args:
            product_type: Product category (e.g., "novel food", "food supplement").
            ingredients: List of ingredient types (e.g., ["food additive", "flavouring"]).
            claims: List of claim types (e.g., ["health claim"]).
            packaging: Packaging type (e.g., "plastic packaging").
            keywords: Additional search terms to match against defined terms.

        Returns:
            RoutingResult with targeted CELEX IDs and reasons.
        """
        result = RoutingResult(celex_ids=[])

        # Always include foundational regulations
        for celex in ALWAYS_INCLUDE:
            title = CORPUS.get(celex, {}).get("title", celex)
            result.add(celex, f"always included ({title})")

        # Collect all input terms to route
        all_terms: list[tuple[str, str]] = []  # (term, source_label)

        if product_type:
            all_terms.append((product_type.lower().strip(), "product type"))

        for ing in (ingredients or []):
            all_terms.append((ing.lower().strip(), "ingredient"))

        for claim in (claims or []):
            all_terms.append((claim.lower().strip(), "claim"))

        if packaging:
            all_terms.append((packaging.lower().strip(), "packaging"))

        for kw in (keywords or []):
            all_terms.append((kw.lower().strip(), "keyword"))

        # Route each term
        for term, source_label in all_terms:
            # 1. Check CATEGORY_ROUTING (manual high-level mapping)
            if term in CATEGORY_ROUTING:
                for cat in CATEGORY_ROUTING[term]:
                    for celex in self._category_to_celex.get(cat, set()):
                        result.add(celex, f"{source_label}: \"{term}\" → category {cat}")

            # 2. Check entity index (defined terms)
            if term in self._term_to_celex:
                for celex in self._term_to_celex[term]:
                    result.add(celex, f"{source_label}: \"{term}\" defined in this regulation")

            # 3. Multi-word containment: if the input term is multi-word AND
            # a defined term contains it as a full sub-phrase, include those regs.
            # E.g., "health claim" matches "reduction of disease risk claim".
            # Single-word terms like "food" are too common for substring matching.
            if " " in term and len(term) > 5:
                for defined_term, celex_set in self._term_to_celex.items():
                    if term in defined_term and term != defined_term:
                        for celex in celex_set:
                            result.add(celex, f"{source_label}: \"{term}\" in \"{defined_term}\"")

        return result

    def route_by_category(self, category: str) -> RoutingResult:
        """Route by regulatory category directly (e.g., "food_additives")."""
        result = RoutingResult(celex_ids=[])
        for celex in ALWAYS_INCLUDE:
            title = CORPUS.get(celex, {}).get("title", celex)
            result.add(celex, f"always included ({title})")

        for celex in self._category_to_celex.get(category, set()):
            result.add(celex, f"category: {category}")

        return result
