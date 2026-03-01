"""
FastAPI REST API for the EU Food Safety Regulatory Intelligence Engine.

Provides a programmatic interface to the same pipeline that powers the Streamlit UI.

Endpoints:
    GET  /health            — Index status and corpus size
    GET  /entities          — Available input options (product types, ingredients, etc.)
    POST /compliance-check  — Run the full pipeline and return structured requirements

Usage:
    uvicorn src.api:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.extraction.schemas import ComplianceRequirement
from src.ingestion.corpus import CATEGORIES, CORPUS
from src.pipeline import INDEX_DIR, VECTORSTORE_DIR, query
from src.retrieval.routing import CATEGORY_ROUTING


# --- Pydantic models ---


class ComplianceCheckRequest(BaseModel):
    """Request body for POST /compliance-check."""

    product_type: str = Field(default="", description="Product category, e.g. 'novel food'")
    ingredients: list[str] | None = Field(default=None, description="Ingredient types")
    claims: list[str] | None = Field(default=None, description="Claim types")
    packaging: str = Field(default="", description="Packaging type")
    keywords: list[str] | None = Field(default=None, description="Additional routing keywords")
    query_text: str = Field(default="", description="Natural language query for search")
    n_results: int = Field(default=10, ge=1, le=50, description="Number of articles to retrieve")
    provider: str = Field(default="anthropic", description="LLM provider")
    api_key: str | None = Field(default=None, description="API key for LLM provider")
    model: str | None = Field(default=None, description="Model override")
    skip_extraction: bool = Field(default=False, description="Skip LLM extraction")


class CrossReferenceResponse(BaseModel):
    expanded_count: int
    expanded_celex_ids: list[str]
    resolved_refs: int
    unresolved_refs: int


class RoutingResponse(BaseModel):
    celex_ids: list[str]
    reasons: dict[str, list[str]]
    regulation_count: int
    cross_references: CrossReferenceResponse


class RetrievalResponse(BaseModel):
    query: str
    results_count: int
    articles: list[dict]


class ExtractionResponse(BaseModel):
    requirements: list[ComplianceRequirement] = Field(default_factory=list)
    requirements_count: int = 0
    articles_processed: int = 0
    skipped: bool = False


class ComplianceCheckResponse(BaseModel):
    routing: RoutingResponse
    retrieval: RetrievalResponse
    extraction: ExtractionResponse


class EntitiesResponse(BaseModel):
    product_types: list[str]
    ingredients: list[str]
    claims: list[str]
    packaging: list[str]
    additional_keywords: list[str]
    categories: dict[str, str]
    corpus_size: int


class HealthResponse(BaseModel):
    status: str
    indexes_ready: bool
    corpus_size: int


# --- App state ---

_indexes_ready = False


def _check_indexes() -> bool:
    """Check if pre-built indexes exist on disk."""
    return (
        (INDEX_DIR / "defined_terms.json").exists()
        and (VECTORSTORE_DIR / "embeddings.npy").exists()
    )


def _build_entities() -> EntitiesResponse:
    """Derive input option lists from CATEGORY_ROUTING."""
    # Group CATEGORY_ROUTING keys by their target regulatory categories
    product_categories = {
        "novel_food", "food_supplements", "food_specific_groups", "organic",
    }
    ingredient_categories = {
        "food_additives", "flavourings", "food_enzymes", "gmo", "fortification",
    }
    claim_categories = {"nutrition_health_claims"}
    packaging_categories = {"food_contact_materials"}

    product_types = []
    ingredients = []
    claims = []
    packaging = []
    additional_keywords = []

    for term, target_cats in CATEGORY_ROUTING.items():
        target_set = set(target_cats)
        if target_set & product_categories:
            product_types.append(term)
        elif target_set & ingredient_categories:
            ingredients.append(term)
        elif target_set & claim_categories:
            claims.append(term)
        elif target_set & packaging_categories:
            packaging.append(term)
        else:
            additional_keywords.append(term)

    return EntitiesResponse(
        product_types=sorted(product_types),
        ingredients=sorted(ingredients),
        claims=sorted(claims),
        packaging=sorted(packaging),
        additional_keywords=sorted(additional_keywords),
        categories=CATEGORIES,
        corpus_size=len(CORPUS),
    )


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _indexes_ready
    _indexes_ready = _check_indexes()
    if not _indexes_ready:
        import logging
        logging.getLogger("uvicorn").warning(
            "Indexes not found. Run 'python -m src.pipeline build' to enable /compliance-check."
        )
    yield


# --- App ---


app = FastAPI(
    title="EU Food Safety Regulatory Intelligence API",
    description="Automated compliance checklist generation for EU food regulations",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok" if _indexes_ready else "degraded",
        indexes_ready=_indexes_ready,
        corpus_size=len(CORPUS),
    )


@app.get("/entities", response_model=EntitiesResponse)
async def entities():
    return _build_entities()


@app.post("/compliance-check", response_model=ComplianceCheckResponse)
async def compliance_check(request: ComplianceCheckRequest):
    # Validate: at least one input parameter is required
    has_input = any([
        request.product_type,
        request.ingredients,
        request.claims,
        request.packaging,
        request.keywords,
        request.query_text,
    ])
    if not has_input:
        raise HTTPException(
            status_code=400,
            detail="At least one input parameter is required "
                   "(product_type, ingredients, claims, packaging, keywords, or query_text).",
        )

    if not _indexes_ready:
        raise HTTPException(
            status_code=503,
            detail="Indexes not built. Run 'python -m src.pipeline build' first.",
        )

    try:
        result = query(
            product_type=request.product_type,
            ingredients=request.ingredients,
            claims=request.claims,
            packaging=request.packaging,
            keywords=request.keywords,
            query_text=request.query_text,
            n_results=request.n_results,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            skip_extraction=request.skip_extraction,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Build typed response from the pipeline output dict
    routing = RoutingResponse(
        celex_ids=result["routing"]["celex_ids"],
        reasons=result["routing"]["reasons"],
        regulation_count=result["routing"]["regulation_count"],
        cross_references=CrossReferenceResponse(**result["routing"]["cross_references"]),
    )

    retrieval = RetrievalResponse(
        query=result["retrieval"]["query"],
        results_count=result["retrieval"]["results_count"],
        articles=result["retrieval"]["articles"],
    )

    extraction_data = result.get("extraction", {})
    extraction = ExtractionResponse(
        requirements=[
            ComplianceRequirement(**r) for r in extraction_data.get("requirements", [])
        ],
        requirements_count=extraction_data.get("requirements_count", 0),
        articles_processed=extraction_data.get("articles_processed", 0),
        skipped=extraction_data.get("skipped", False),
    )

    return ComplianceCheckResponse(
        routing=routing,
        retrieval=retrieval,
        extraction=extraction,
    )
