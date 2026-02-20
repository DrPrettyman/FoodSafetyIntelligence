"""
End-to-end evaluation scenarios for the regulatory intelligence pipeline.

Tests the full pipeline: structured input → routing → vector search → relevant articles.
Each scenario represents a real-world product compliance query and verifies that:
1. The routing table selects the correct regulations
2. The vector store returns semantically relevant articles
3. Key regulatory requirements are surfaced

These are integration tests that require the downloaded corpus and built vector store.
"""

import tempfile
import warnings
from pathlib import Path

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from src.extraction.entity_extractor import extract_entities
from src.indexing.vector_store import VectorStore
from src.ingestion.html_parser import parse_corpus
from src.retrieval.chunking import chunk_corpus
from src.retrieval.routing import RoutingTable

SAMPLE_DIR = Path("data/raw/html")
has_samples = SAMPLE_DIR.exists() and any(SAMPLE_DIR.glob("*.html"))


@pytest.fixture(scope="module")
def pipeline():
    """Build the full pipeline once for all evaluation tests."""
    if not has_samples:
        pytest.skip("No sample HTML files downloaded")

    regulations = parse_corpus()
    entity_index = extract_entities(regulations)
    chunks = chunk_corpus(regulations)
    routing_table = RoutingTable(entity_index)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=tmpdir)
        store.index_chunks(chunks)
        yield {
            "routing_table": routing_table,
            "store": store,
            "entity_index": entity_index,
            "chunk_count": len(chunks),
        }


def _run_scenario(pipeline, product_type="", ingredients=None, claims=None,
                  packaging="", keywords=None, query="", n_results=10):
    """Helper to run a full pipeline scenario."""
    rt = pipeline["routing_table"]
    store = pipeline["store"]

    # Step 1: Route to relevant regulations
    routing_result = rt.route(
        product_type=product_type,
        ingredients=ingredients,
        claims=claims,
        packaging=packaging,
        keywords=keywords,
    )

    # Step 2: Search vector store filtered to routed regulations
    search_results = store.search(
        query=query,
        celex_ids=routing_result.celex_ids,
        n_results=n_results,
    )

    return {
        "routing": routing_result,
        "results": search_results,
        "routed_celex_count": len(routing_result.celex_ids),
    }


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestEvaluation:
    """5 real-world evaluation scenarios."""

    def test_scenario_1_novel_food_insect_protein(self, pipeline):
        """Scenario: Insect protein bar — novel food with specific labelling requirements.

        Expected: Novel food regulations, labelling rules, and allergen provisions.
        Key articles: Novel Foods Reg Art 1 (scope), Art 3 (definitions),
                     FIC Reg Art 9 (mandatory info), Art 21 (allergens).
        """
        out = _run_scenario(
            pipeline,
            product_type="novel food",
            query="insect protein novel food labelling allergen requirements",
        )

        # Routing should include novel food and labelling regulations
        celex_set = set(out["routing"].celex_ids)
        assert "32015R2283" in celex_set, "Should route to Novel Foods Regulation"
        assert "32011R1169" in celex_set, "Should route to FIC (labelling)"

        # Search results should contain relevant articles
        result_celex = {r["metadata"]["celex_id"] for r in out["results"]}
        assert len(out["results"]) > 0
        # At least one result from novel food or labelling regulation
        assert result_celex & {"32015R2283", "32011R1169"}, \
            f"Results should include novel food or FIC articles, got: {result_celex}"

    def test_scenario_2_food_supplement_vitamins(self, pipeline):
        """Scenario: Vitamin D supplement — food supplement with health claims.

        Expected: Food supplements directive, fortification regulation,
                 nutrition/health claims regulation.
        """
        out = _run_scenario(
            pipeline,
            product_type="food supplement",
            ingredients=["vitamin"],
            claims=["health claim"],
            query="vitamin D food supplement permitted health claim dosage",
        )

        celex_set = set(out["routing"].celex_ids)
        assert "32002L0046" in celex_set, "Should route to Food Supplements Directive"
        assert "32006R1924" in celex_set, "Should route to Health Claims Regulation"
        assert "32006R1925" in celex_set, "Should route to Fortification Regulation"

        assert len(out["results"]) > 0

    def test_scenario_3_food_additive_plastic_packaging(self, pipeline):
        """Scenario: Beverage with sweetener in plastic bottle.

        Expected: Food additives regulation, plastic FCM regulation, labelling.
        """
        out = _run_scenario(
            pipeline,
            ingredients=["food additive"],
            packaging="plastic packaging",
            query="sweetener food additive plastic migration limit labelling",
        )

        celex_set = set(out["routing"].celex_ids)
        assert "32008R1333" in celex_set, "Should route to Food Additives Regulation"
        assert "32011R0010" in celex_set, "Should route to Plastic FCM Regulation"
        assert "32011R1169" in celex_set, "Should route to FIC (labelling)"

        # Results should have articles about additives or packaging
        assert len(out["results"]) > 0
        result_celex = {r["metadata"]["celex_id"] for r in out["results"]}
        assert result_celex & {"32008R1333", "32011R0010"}, \
            f"Results should include additive or FCM articles, got: {result_celex}"

    def test_scenario_4_gmo_traceability(self, pipeline):
        """Scenario: Product containing GMO soy — traceability and labelling.

        Expected: GMO food/feed regulation, traceability regulation, labelling.
        """
        out = _run_scenario(
            pipeline,
            keywords=["gmo"],
            query="genetically modified organism traceability labelling threshold",
        )

        celex_set = set(out["routing"].celex_ids)
        assert "32003R1829" in celex_set, "Should route to GM Food and Feed Regulation"
        assert "32003R1830" in celex_set, "Should route to GMO Traceability Regulation"

        assert len(out["results"]) > 0
        result_celex = {r["metadata"]["celex_id"] for r in out["results"]}
        assert result_celex & {"32003R1829", "32003R1830"}, \
            f"Results should include GMO articles, got: {result_celex}"

    def test_scenario_5_organic_food_contaminants(self, pipeline):
        """Scenario: Organic cereal product — organic rules + contaminant limits.

        Expected: Organic regulation, contaminants regulation, general food law.
        """
        out = _run_scenario(
            pipeline,
            product_type="organic food",
            keywords=["contaminant"],
            query="organic production rules maximum contaminant levels cereals",
        )

        celex_set = set(out["routing"].celex_ids)
        assert "32018R0848" in celex_set, "Should route to Organic Regulation"
        assert "32023R0915" in celex_set or "32006R1881" in celex_set, \
            "Should route to a contaminants regulation"
        assert "32002R0178" in celex_set, "Should include General Food Law"

        assert len(out["results"]) > 0

    # --- Pipeline quality metrics ---

    def test_routing_precision(self, pipeline):
        """Routing should not return the entire corpus for a focused query."""
        out = _run_scenario(
            pipeline,
            product_type="novel food",
            query="novel food application procedure",
        )
        # A focused query should return a subset, not all 33 regulations
        total_corpus = 33
        assert out["routed_celex_count"] < total_corpus * 0.5, \
            f"Routing returned {out['routed_celex_count']}/{total_corpus} regulations — too broad"

    def test_filtered_vs_unfiltered_relevance(self, pipeline):
        """Filtered search (with routing) should return more relevant results."""
        store = pipeline["store"]
        rt = pipeline["routing_table"]

        query = "food additive maximum permitted levels in beverages"

        # Unfiltered search
        unfiltered = store.search(query, n_results=5)

        # Filtered search via routing
        routing = rt.route(ingredients=["food additive"])
        filtered = store.search(query, celex_ids=routing.celex_ids, n_results=5)

        # Filtered results should have food additive articles more prominently
        filtered_additive = sum(
            1 for r in filtered
            if r["metadata"]["celex_id"] == "32008R1333"
        )
        unfiltered_additive = sum(
            1 for r in unfiltered
            if r["metadata"]["celex_id"] == "32008R1333"
        )

        assert filtered_additive >= unfiltered_additive, \
            "Filtered search should surface food additive articles at least as well"
