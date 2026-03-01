"""
Tests for the end-to-end pipeline and index serialization.

Tests cover:
1. Entity index serialization (save/load round-trip)
2. Build phase (with real corpus if available)
3. Query phase (routing + retrieval, LLM extraction mocked)
4. CLI argument parsing
"""

import json
import tempfile
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from src.extraction.entity_extractor import CrossReference, DefinedTerm, EntityIndex
from src.pipeline import (
    build_indexes,
    load_entity_index,
    query,
    save_entity_index,
)

SAMPLE_DIR = Path("data/raw/html")
has_samples = SAMPLE_DIR.exists() and any(SAMPLE_DIR.glob("*.html"))


# --- Serialization tests ---


class TestEntityIndexSerialization:
    """Test save/load round-trip for entity indexes."""

    def _make_entity_index(self) -> EntityIndex:
        """Create a small test entity index."""
        return EntityIndex(
            defined_terms=[
                DefinedTerm(
                    term="novel food",
                    celex_id="32015R2283",
                    article_number=3,
                    definition_snippet="any food that was not used ...",
                    category="novel_food",
                ),
                DefinedTerm(
                    term="food additive",
                    celex_id="32008R1333",
                    article_number=3,
                    definition_snippet="any substance not normally consumed ...",
                    category="food_additives",
                ),
            ],
            cross_references=[
                CrossReference(
                    source_celex="32015R2283",
                    source_article=4,
                    target_regulation_number="178/2002",
                    context="as defined in Regulation (EC) No 178/2002",
                ),
            ],
        )

    def test_save_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index = self._make_entity_index()
            save_entity_index(index, Path(tmpdir))

            assert (Path(tmpdir) / "defined_terms.json").exists()
            assert (Path(tmpdir) / "cross_references.json").exists()
            assert (Path(tmpdir) / "entity_stats.json").exists()

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = self._make_entity_index()
            save_entity_index(original, Path(tmpdir))
            loaded = load_entity_index(Path(tmpdir))

            assert len(loaded.defined_terms) == len(original.defined_terms)
            assert len(loaded.cross_references) == len(original.cross_references)

            # Check first term
            assert loaded.defined_terms[0].term == "novel food"
            assert loaded.defined_terms[0].celex_id == "32015R2283"
            assert loaded.defined_terms[0].category == "novel_food"

            # Check cross-reference
            assert loaded.cross_references[0].target_regulation_number == "178/2002"

    def test_stats_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index = self._make_entity_index()
            save_entity_index(index, Path(tmpdir))

            with open(Path(tmpdir) / "entity_stats.json") as f:
                stats = json.load(f)

            assert stats["total_defined_terms"] == 2
            assert stats["unique_terms"] == 2
            assert stats["total_cross_references"] == 1

    def test_load_missing_files_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError, match="Entity index not found"):
                load_entity_index(Path(tmpdir))

    def test_unicode_preservation(self):
        """Terms with unicode characters should survive serialization."""
        index = EntityIndex(
            defined_terms=[
                DefinedTerm(
                    term="«novel food»",
                    celex_id="32015R2283",
                    article_number=3,
                    definition_snippet="means any food…",
                    category="novel_food",
                ),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            save_entity_index(index, Path(tmpdir))
            loaded = load_entity_index(Path(tmpdir))
            assert loaded.defined_terms[0].term == "«novel food»"


# --- Build phase tests ---


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestBuildIndexes:
    """Test the full build phase with real corpus data."""

    def test_build_creates_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vs_dir = Path(tmpdir) / "vectorstore"
            idx_dir = Path(tmpdir) / "indexes"

            summary = build_indexes(vectorstore_dir=vs_dir, index_dir=idx_dir)

            # Check summary
            assert summary["regulations"] > 0
            assert summary["articles"] > 0
            assert summary["chunks"] > 0
            assert summary["defined_terms"] > 0
            assert summary["indexed_chunks"] > 0

            # Check files exist
            assert (idx_dir / "defined_terms.json").exists()
            assert (idx_dir / "cross_references.json").exists()
            assert (idx_dir / "entity_stats.json").exists()
            assert (idx_dir / "build_summary.json").exists()
            assert (vs_dir / "embeddings.npy").exists()
            assert (vs_dir / "metadata.json").exists()


# --- Query phase tests ---


@pytest.mark.skipif(not has_samples, reason="No sample HTML files downloaded")
class TestQuery:
    """Test the query phase with real indexes."""

    @pytest.fixture(scope="class")
    def built_indexes(self, tmp_path_factory):
        """Build indexes once for all query tests in this class."""
        tmpdir = tmp_path_factory.mktemp("pipeline")
        vs_dir = tmpdir / "vectorstore"
        idx_dir = tmpdir / "indexes"
        build_indexes(vectorstore_dir=vs_dir, index_dir=idx_dir)
        return vs_dir, idx_dir

    def test_query_routing_only(self, built_indexes):
        """Query with skip_extraction should return routing + retrieval only."""
        vs_dir, idx_dir = built_indexes
        result = query(
            product_type="novel food",
            query_text="novel food requirements",
            skip_extraction=True,
            vectorstore_dir=vs_dir,
            index_dir=idx_dir,
        )

        assert "routing" in result
        assert "retrieval" in result
        assert result["extraction"]["skipped"] is True
        assert result["routing"]["regulation_count"] > 0
        assert result["retrieval"]["results_count"] > 0

        # Should include novel food regulation
        assert "32015R2283" in result["routing"]["celex_ids"]

    def test_query_builds_query_from_params(self, built_indexes):
        """When no query_text given, should build one from parameters."""
        vs_dir, idx_dir = built_indexes
        result = query(
            product_type="food supplement",
            ingredients=["vitamin"],
            skip_extraction=True,
            vectorstore_dir=vs_dir,
            index_dir=idx_dir,
        )

        assert "food supplement" in result["retrieval"]["query"]
        assert "vitamin" in result["retrieval"]["query"]

    @patch("src.pipeline.extract_requirements")
    def test_query_with_extraction(self, mock_extract, built_indexes):
        """Query with LLM extraction (mocked)."""
        from src.extraction.schemas import (
            ComplianceRequirement,
            ExtractionResult,
            Priority,
            RequirementType,
        )

        mock_extract.return_value = ExtractionResult(
            requirements=[
                ComplianceRequirement(
                    regulation_id="32015R2283",
                    article_number=7,
                    article_title="General conditions",
                    requirement_summary="Novel food must be authorised.",
                    requirement_type=RequirementType.AUTHORISATION,
                    priority=Priority.BEFORE_LAUNCH,
                    confidence=0.95,
                ),
            ],
            articles_processed=5,
            product_context="novel food",
        )

        vs_dir, idx_dir = built_indexes
        result = query(
            product_type="novel food",
            query_text="novel food authorisation",
            api_key="test-key",
            vectorstore_dir=vs_dir,
            index_dir=idx_dir,
        )

        assert result["extraction"]["requirements_count"] == 1
        assert result["extraction"]["requirements"][0]["regulation_id"] == "32015R2283"
        mock_extract.assert_called_once()

    def test_query_empty_store_raises(self):
        """Query against an empty store should raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vs_dir = Path(tmpdir) / "empty_vs"
            vs_dir.mkdir()
            idx_dir = Path(tmpdir) / "indexes"
            # Need entity index files
            save_entity_index(EntityIndex(), idx_dir)

            with pytest.raises(RuntimeError, match="Vector store is empty"):
                query(
                    product_type="novel food",
                    skip_extraction=True,
                    vectorstore_dir=vs_dir,
                    index_dir=idx_dir,
                )


# --- Tiered retrieval tests ---


class TestTieredRetrieval:
    """Verify that core regulations get more search budget than cross-ref expansions."""

    def _make_hit(self, celex_id: str, art: int, score: float = 0.5) -> dict:
        """Build a synthetic search result."""
        return {
            "chunk_id": f"{celex_id}_art{art}_chunk0",
            "text": f"Article {art} text...",
            "metadata": {
                "celex_id": celex_id,
                "article_number": art,
                "article_title": f"Article {art}",
                "chapter": "",
                "section": "",
                "chunk_index": 0,
                "total_chunks": 1,
            },
            "score": score,
        }

    @patch("src.pipeline.CrossReferenceIndex")
    @patch("src.pipeline.RoutingTable")
    @patch("src.pipeline.VectorStore")
    @patch("src.pipeline.load_entity_index")
    def test_core_regs_get_more_articles_than_xref(
        self, mock_load_idx, mock_vs_cls, mock_rt_cls, mock_xref_cls
    ):
        """Core regulations should be searched with higher n_results than xref regs."""
        # Setup entity index
        mock_load_idx.return_value = EntityIndex()

        # Setup routing: returns 3 core regulations
        from src.retrieval.routing import RoutingResult

        routing_result = RoutingResult(celex_ids=[])
        routing_result.add("32015R2283", "product type: novel food")
        routing_result.add("32002R0178", "always included (General Food Law)")
        routing_result.add("32011R1169", "keyword: labelling")
        mock_rt_cls.return_value.route.return_value = routing_result

        # Setup cross-reference expansion: adds 2 xref regulations
        xref_new_ids = ["32008R1332", "32003R1829"]
        xref_reasons = {
            "32008R1332": ["cross-referenced from 32015R2283"],
            "32003R1829": ["cross-referenced from 32015R2283"],
        }
        mock_xref_build = MagicMock()
        mock_xref_build.expand.return_value = (xref_new_ids, xref_reasons)
        mock_xref_cls.build.return_value = mock_xref_build

        # Setup vector store — return different hits for each search call
        mock_store = MagicMock()
        mock_store.count = 100

        call_log = []

        def mock_search(query, celex_ids, n_results):
            call_log.append({"celex_ids": celex_ids, "n_results": n_results})
            # Return one unique hit per call
            cid = celex_ids[0] if len(celex_ids) == 1 else "broad"
            return [self._make_hit(cid, n_results, score=0.5)]

        mock_store.search.side_effect = mock_search
        mock_vs_cls.return_value = mock_store

        # Run query
        result = query(
            product_type="novel food",
            query_text="novel food requirements",
            n_results=10,
            skip_extraction=True,
            vectorstore_dir=Path("/tmp/fake_vs"),
            index_dir=Path("/tmp/fake_idx"),
        )

        # Verify call pattern:
        # call_log[0] = broad search (all 5 celex_ids)
        # call_log[1..3] = core per-reg searches (3 core regs)
        # call_log[4..5] = xref per-reg searches (2 xref regs)
        assert len(call_log) == 6  # 1 broad + 3 core + 2 xref

        broad_call = call_log[0]
        assert len(broad_call["celex_ids"]) == 5  # all regulations

        # Core calls should have n_results >= 3
        core_calls = call_log[1:4]
        for call in core_calls:
            assert len(call["celex_ids"]) == 1
            assert call["celex_ids"][0] not in xref_new_ids
            assert call["n_results"] >= 3

        # Xref calls should have n_results == 1
        xref_calls = call_log[4:6]
        for call in xref_calls:
            assert len(call["celex_ids"]) == 1
            assert call["celex_ids"][0] in xref_new_ids
            assert call["n_results"] == 1

    @patch("src.pipeline.CrossReferenceIndex")
    @patch("src.pipeline.RoutingTable")
    @patch("src.pipeline.VectorStore")
    @patch("src.pipeline.load_entity_index")
    def test_no_xref_all_budget_to_core(
        self, mock_load_idx, mock_vs_cls, mock_rt_cls, mock_xref_cls
    ):
        """When there are no cross-ref expansions, all budget goes to core regs."""
        mock_load_idx.return_value = EntityIndex()

        from src.retrieval.routing import RoutingResult

        routing_result = RoutingResult(celex_ids=[])
        routing_result.add("32015R2283", "product type: novel food")
        routing_result.add("32002R0178", "always included")
        mock_rt_cls.return_value.route.return_value = routing_result

        # No cross-ref expansion
        mock_xref_build = MagicMock()
        mock_xref_build.expand.return_value = ([], {})
        mock_xref_cls.build.return_value = mock_xref_build

        mock_store = MagicMock()
        mock_store.count = 100
        call_log = []

        def mock_search(query, celex_ids, n_results):
            call_log.append({"celex_ids": celex_ids, "n_results": n_results})
            cid = celex_ids[0] if len(celex_ids) == 1 else "broad"
            return [self._make_hit(cid, n_results, score=0.5)]

        mock_store.search.side_effect = mock_search
        mock_vs_cls.return_value = mock_store

        result = query(
            product_type="novel food",
            query_text="novel food requirements",
            n_results=10,
            skip_extraction=True,
            vectorstore_dir=Path("/tmp/fake_vs"),
            index_dir=Path("/tmp/fake_idx"),
        )

        # 1 broad + 2 core + 0 xref = 3 calls
        assert len(call_log) == 3

        # Core regs should get n_results // 2 = 5, or at least 3
        core_calls = call_log[1:3]
        for call in core_calls:
            assert call["n_results"] == 5  # 10 // 2 = 5

    @patch("src.pipeline.CrossReferenceIndex")
    @patch("src.pipeline.RoutingTable")
    @patch("src.pipeline.VectorStore")
    @patch("src.pipeline.load_entity_index")
    def test_deduplication_across_tiers(
        self, mock_load_idx, mock_vs_cls, mock_rt_cls, mock_xref_cls
    ):
        """Duplicate chunk_ids across broad and per-reg searches should be deduplicated."""
        mock_load_idx.return_value = EntityIndex()

        from src.retrieval.routing import RoutingResult

        routing_result = RoutingResult(celex_ids=[])
        routing_result.add("32015R2283", "product type: novel food")
        mock_rt_cls.return_value.route.return_value = routing_result

        mock_xref_build = MagicMock()
        mock_xref_build.expand.return_value = ([], {})
        mock_xref_cls.build.return_value = mock_xref_build

        mock_store = MagicMock()
        mock_store.count = 100

        # Every search returns the same hit — should appear only once in results
        shared_hit = self._make_hit("32015R2283", 7, score=0.9)
        mock_store.search.return_value = [shared_hit]
        mock_vs_cls.return_value = mock_store

        result = query(
            product_type="novel food",
            query_text="novel food requirements",
            skip_extraction=True,
            vectorstore_dir=Path("/tmp/fake_vs"),
            index_dir=Path("/tmp/fake_idx"),
        )

        # Despite multiple search calls returning the same hit, it should appear once
        articles = result["retrieval"]["articles"]
        chunk_ids = [a["chunk_id"] for a in articles]
        assert len(chunk_ids) == len(set(chunk_ids))
