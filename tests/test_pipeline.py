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
