# EU Food Safety Regulatory Intelligence Engine

Given a food product's category, ingredients, claims, and packaging, generates a compliance checklist citing specific EU regulation articles.

## The Problem

Launching a food product into the EU means complying with regulations spread across dozens of legal acts. A protein bar with a novel ingredient like insect flour touches 15+ acts — novel food authorisation, allergen labelling, health claims, food contact materials. Regulatory consultants charge €300-500/hour to answer "what do I need to comply with?"

## What This Builds

A pipeline that takes structured product parameters and returns a compliance checklist with article-level citations. The system routes to applicable regulations deterministically (no LLM in the loop for retrieval), then uses an LLM to extract structured requirements from the matched articles.

```
EUR-Lex HTML → Parse (4 formats) → Chunk → Extract Entities
    → Route to Regulations → Semantic Search → LLM Extract → Compliance Checklist
```

## Key Results

| Metric | Value |
|--------|-------|
| Regulations in corpus | 243 across 17 categories |
| Articles parsed | 2,823 |
| Defined terms extracted | 702 (475 unique) |
| Cross-references indexed | 1,032 |
| Evaluation scenarios | 3 (52 ground-truth requirements) |
| **Precision** | **0.58** |
| **Recall** | **0.69** |
| **F1** | **0.63** |
| Hallucination rate | 0% |
| Tests | 304 passing |

Every false negative is a retrieval failure (relevant article ranked outside the search window), not an extraction error. The LLM never hallucinated a regulation — it only extracts from what the routing layer selects.

## Quick Start

```bash
docker compose up
# Streamlit UI: http://localhost:8501
# REST API:    http://localhost:8000/docs
```

Or manually:

```bash
pip install -e .
python -m src.pipeline build    # one-time: parse corpus, build indexes (~30s)
streamlit run app.py             # or: uvicorn src.api:app
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Index status and corpus size |
| `/entities` | GET | Available input options (product types, ingredients, claims) |
| `/compliance-check` | POST | Run pipeline, return structured requirements |

## Tech Stack

Python, sentence-transformers, NumPy, Anthropic API (tool_use), FastAPI, Streamlit, Docker

## Evaluation Approach

Four layers:

1. **Entity coverage** — Do extracted defined terms cover the corpus?
2. **Routing accuracy** — Does deterministic routing select the right regulations for a product?
3. **Retrieval recall** — Do the top-N articles contain the ones a compliance officer would cite?
4. **Extraction P/R/F1** — Against hand-labelled ground truth, with failure mode classification into retrieval_failure, tangential_cross_ref, over_extraction, scope_error, and hallucination

## Limitations

- **Small ground truth** — 52 requirements across 3 scenarios validates the approach and identifies failure modes, but isn't large enough for statistical confidence.
- **Retrieval is the bottleneck** — all false negatives trace back to relevant articles ranking outside the search window. Extraction quality is not the limiting factor.
- **Cross-reference noise** — 1-hop regulation expansion adds tangential results (56% of false positives).
- **Non-deterministic extraction** — repeated runs with the same LLM produce slightly different outputs, making before/after metric comparisons noisy.

## What I'd Do Next

- Expand ground truth to 20-30 scenarios for robust evaluation
- Re-rank retrieved articles before extraction (cross-encoder or LLM-based)
- Add regulation-level confidence scoring to reduce cross-reference noise
- Deploy to cloud with persistent storage and API authentication
