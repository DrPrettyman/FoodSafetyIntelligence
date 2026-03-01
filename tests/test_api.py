"""
Tests for the FastAPI REST API.

Tests cover:
1. GET /health — status with and without indexes
2. GET /entities — returns all input option fields
3. POST /compliance-check — success, validation, error handling, param forwarding
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.retrieval.routing import CATEGORY_ROUTING

# Sample pipeline output matching the shape returned by query()
MOCK_QUERY_RESULT = {
    "routing": {
        "celex_ids": ["32015R2283", "32002R0178"],
        "reasons": {
            "32015R2283": ['product type: "novel food" → category novel_food'],
            "32002R0178": ["always included (General Food Law)"],
        },
        "regulation_count": 2,
        "cross_references": {
            "expanded_count": 0,
            "expanded_celex_ids": [],
            "resolved_refs": 0,
            "unresolved_refs": 0,
        },
    },
    "retrieval": {
        "query": "novel food requirements",
        "results_count": 1,
        "articles": [
            {
                "chunk_id": "32015R2283_art7_chunk0",
                "text": "Article 7 text...",
                "metadata": {
                    "celex_id": "32015R2283",
                    "article_number": 7,
                    "article_title": "General conditions",
                },
                "score": 0.85,
            },
        ],
    },
    "extraction": {
        "requirements": [
            {
                "regulation_id": "32015R2283",
                "article_number": 7,
                "article_title": "General conditions",
                "requirement_summary": "Novel food must be authorised before placing on the market.",
                "requirement_type": "authorisation",
                "priority": "before_launch",
                "applicable_to": "",
                "conditions": "",
                "cross_references": [],
                "source_text_snippet": "",
                "confidence": 0.95,
            },
        ],
        "requirements_count": 1,
        "articles_processed": 1,
    },
}

MOCK_QUERY_RESULT_SKIPPED = {
    "routing": MOCK_QUERY_RESULT["routing"],
    "retrieval": MOCK_QUERY_RESULT["retrieval"],
    "extraction": {"skipped": True},
}


@pytest.fixture
def client():
    """TestClient with indexes marked as ready."""
    with patch("src.api._check_indexes", return_value=True):
        from src.api import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_no_indexes():
    """TestClient with indexes marked as NOT ready."""
    with patch("src.api._check_indexes", return_value=False):
        from src.api import app
        with TestClient(app) as c:
            yield c


# --- Health ---


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["indexes_ready"] is True
        assert data["corpus_size"] > 0

    def test_health_degraded(self, client_no_indexes):
        resp = client_no_indexes.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["indexes_ready"] is False


# --- Entities ---


class TestEntities:
    def test_entities_returns_all_fields(self, client):
        resp = client.get("/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert "product_types" in data
        assert "ingredients" in data
        assert "claims" in data
        assert "packaging" in data
        assert "additional_keywords" in data
        assert "categories" in data
        assert "corpus_size" in data

    def test_entities_lists_non_empty(self, client):
        resp = client.get("/entities")
        data = resp.json()
        assert len(data["product_types"]) > 0
        assert len(data["ingredients"]) > 0
        assert len(data["claims"]) > 0
        assert len(data["packaging"]) > 0
        assert len(data["categories"]) > 0
        assert data["corpus_size"] > 0

    def test_entities_covers_all_routing_keys(self, client):
        """Every key in CATEGORY_ROUTING should appear in exactly one list."""
        resp = client.get("/entities")
        data = resp.json()
        all_terms = set(
            data["product_types"]
            + data["ingredients"]
            + data["claims"]
            + data["packaging"]
            + data["additional_keywords"]
        )
        for key in CATEGORY_ROUTING:
            assert key in all_terms, f"CATEGORY_ROUTING key '{key}' not in any entity list"


# --- Compliance Check ---


class TestComplianceCheck:
    @patch("src.api.query", return_value=MOCK_QUERY_RESULT)
    def test_success_with_extraction(self, mock_query, client):
        resp = client.post(
            "/compliance-check",
            json={"product_type": "novel food", "query_text": "novel food requirements"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["routing"]["regulation_count"] == 2
        assert data["retrieval"]["results_count"] == 1
        assert data["extraction"]["requirements_count"] == 1
        assert data["extraction"]["requirements"][0]["regulation_id"] == "32015R2283"

    @patch("src.api.query", return_value=MOCK_QUERY_RESULT_SKIPPED)
    def test_success_skip_extraction(self, mock_query, client):
        resp = client.post(
            "/compliance-check",
            json={"product_type": "novel food", "skip_extraction": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction"]["skipped"] is True
        assert data["extraction"]["requirements"] == []

    def test_no_input_returns_400(self, client):
        resp = client.post("/compliance-check", json={})
        assert resp.status_code == 400
        assert "At least one input" in resp.json()["detail"]

    def test_missing_indexes_returns_503(self, client_no_indexes):
        resp = client_no_indexes.post(
            "/compliance-check",
            json={"product_type": "novel food"},
        )
        assert resp.status_code == 503
        assert "Indexes not built" in resp.json()["detail"]

    @patch("src.api.query", side_effect=ValueError("Invalid provider"))
    def test_value_error_returns_400(self, mock_query, client):
        resp = client.post(
            "/compliance-check",
            json={"product_type": "novel food"},
        )
        assert resp.status_code == 400
        assert "Invalid provider" in resp.json()["detail"]

    @patch("src.api.query", side_effect=RuntimeError("Vector store is empty"))
    def test_runtime_error_returns_503(self, mock_query, client):
        resp = client.post(
            "/compliance-check",
            json={"product_type": "novel food"},
        )
        assert resp.status_code == 503
        assert "Vector store is empty" in resp.json()["detail"]

    @patch("src.api.query", return_value=MOCK_QUERY_RESULT)
    def test_params_forwarded_to_query(self, mock_query, client):
        """All request fields should be forwarded to query()."""
        resp = client.post(
            "/compliance-check",
            json={
                "product_type": "food supplement",
                "ingredients": ["vitamin", "mineral"],
                "claims": ["health claim"],
                "packaging": "plastic packaging",
                "keywords": ["gmo"],
                "query_text": "supplement requirements",
                "n_results": 15,
                "provider": "openai",
                "api_key": "test-key",
                "model": "gpt-4",
                "skip_extraction": True,
            },
        )
        assert resp.status_code == 200
        mock_query.assert_called_once_with(
            product_type="food supplement",
            ingredients=["vitamin", "mineral"],
            claims=["health claim"],
            packaging="plastic packaging",
            keywords=["gmo"],
            query_text="supplement requirements",
            n_results=15,
            provider="openai",
            api_key="test-key",
            model="gpt-4",
            skip_extraction=True,
        )
