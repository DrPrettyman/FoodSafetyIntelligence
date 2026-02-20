import warnings
from pathlib import Path

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.extraction.entity_extractor import EntityIndex, DefinedTerm
from src.retrieval.routing import (
    ALWAYS_INCLUDE,
    CATEGORY_ROUTING,
    RoutingResult,
    RoutingTable,
)


# --- RoutingResult tests ---


def test_routing_result_add():
    result = RoutingResult(celex_ids=[])
    result.add("32002R0178", "always included")
    result.add("32002R0178", "keyword match")
    assert result.celex_ids == ["32002R0178"]
    assert len(result.reasons["32002R0178"]) == 2


def test_routing_result_no_duplicate_celex():
    result = RoutingResult(celex_ids=[])
    result.add("32002R0178", "reason1")
    result.add("32002R0178", "reason2")
    assert result.celex_ids.count("32002R0178") == 1


def test_routing_result_no_duplicate_reasons():
    result = RoutingResult(celex_ids=[])
    result.add("32002R0178", "same reason")
    result.add("32002R0178", "same reason")
    assert len(result.reasons["32002R0178"]) == 1


# --- RoutingTable without entity index ---


def test_routing_table_without_entities():
    rt = RoutingTable()
    assert len(rt.available_categories) > 0
    assert len(rt.regulatory_categories) > 0
    assert len(rt.available_terms) == 0  # no entity index


def test_always_includes_foundational():
    rt = RoutingTable()
    result = rt.route()
    for celex in ALWAYS_INCLUDE:
        assert celex in result.celex_ids


def test_route_by_product_type():
    rt = RoutingTable()
    result = rt.route(product_type="novel food")
    assert "32015R2283" in result.celex_ids  # Novel Foods Regulation


def test_route_by_ingredient():
    rt = RoutingTable()
    result = rt.route(ingredients=["food additive"])
    assert "32008R1333" in result.celex_ids  # Food Additives Regulation


def test_route_by_claim():
    rt = RoutingTable()
    result = rt.route(claims=["health claim"])
    assert "32006R1924" in result.celex_ids  # Nutrition and Health Claims


def test_route_by_packaging():
    rt = RoutingTable()
    result = rt.route(packaging="plastic packaging")
    assert "32011R0010" in result.celex_ids  # Plastic FCM


def test_route_by_category():
    rt = RoutingTable()
    result = rt.route_by_category("gmo")
    assert "32003R1829" in result.celex_ids  # GM Food and Feed
    assert "32003R1830" in result.celex_ids  # Traceability and labelling of GMOs


def test_route_empty_params_returns_foundational_only():
    rt = RoutingTable()
    result = rt.route()
    # With no params, only foundational regulations should be included
    assert set(result.celex_ids) == ALWAYS_INCLUDE


def test_all_category_routing_keys_are_lowercase():
    for key in CATEGORY_ROUTING:
        assert key == key.lower(), f"CATEGORY_ROUTING key '{key}' should be lowercase"


# --- RoutingTable with entity index ---


@pytest.fixture
def mock_entity_index():
    return EntityIndex(
        defined_terms=[
            DefinedTerm(
                term="novel food",
                celex_id="32015R2283",
                article_number=3,
                definition_snippet="...",
                category="novel_food",
            ),
            DefinedTerm(
                term="food additive",
                celex_id="32008R1333",
                article_number=3,
                definition_snippet="...",
                category="food_additives",
            ),
            DefinedTerm(
                term="food enzyme",
                celex_id="32008R1332",
                article_number=3,
                definition_snippet="...",
                category="food_enzymes",
            ),
        ]
    )


def test_route_with_entity_index(mock_entity_index):
    rt = RoutingTable(mock_entity_index)
    assert len(rt.available_terms) == 3

    result = rt.route(keywords=["food additive"])
    assert "32008R1333" in result.celex_ids


def test_entity_exact_match(mock_entity_index):
    rt = RoutingTable(mock_entity_index)
    result = rt.route(product_type="novel food")
    reasons = result.reasons.get("32015R2283", [])
    assert any("defined in this regulation" in r for r in reasons)


# --- Live corpus integration tests ---

SAMPLE_DIR = Path("data/raw/html")
has_samples = SAMPLE_DIR.exists() and any(SAMPLE_DIR.glob("*.html"))


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestLiveRouting:
    @pytest.fixture(autouse=True)
    def setup_routing_table(self):
        from src.ingestion.html_parser import parse_corpus
        from src.extraction.entity_extractor import extract_entities

        regulations = parse_corpus()
        entity_index = extract_entities(regulations)
        self.rt = RoutingTable(entity_index)

    def test_novel_food_routes_correctly(self):
        result = self.rt.route(product_type="novel food")
        assert "32015R2283" in result.celex_ids
        assert "32017R2470" in result.celex_ids  # Union List

    def test_food_supplement_routes_correctly(self):
        result = self.rt.route(product_type="food supplement")
        assert "32002L0046" in result.celex_ids

    def test_gmo_routes_correctly(self):
        result = self.rt.route(keywords=["gmo"])
        assert "32003R1829" in result.celex_ids
        assert "32003R1830" in result.celex_ids

    def test_combined_query_includes_all_relevant(self):
        result = self.rt.route(
            product_type="novel food",
            ingredients=["food additive"],
            claims=["health claim"],
        )
        # Should include novel food, food additive, and health claims regulations
        assert "32015R2283" in result.celex_ids
        assert "32008R1333" in result.celex_ids
        assert "32006R1924" in result.celex_ids

    def test_reasons_explain_routing(self):
        result = self.rt.route(product_type="novel food")
        reasons = result.reasons.get("32015R2283", [])
        assert len(reasons) > 0
        # Should explain why this regulation was included
        assert any("novel food" in r for r in reasons)
