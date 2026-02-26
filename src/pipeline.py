"""
End-to-end regulatory intelligence pipeline.

Two phases:
1. **Build phase** (offline, run once): parse corpus → chunk → extract entities →
   build routing table → build vector store → serialize indexes to disk.
2. **Query phase** (runtime): load indexes → route structured query → search
   vector store → extract requirements via LLM → return compliance checklist.

Usage:
    # Build indexes (run once after downloading the corpus)
    python -m src.pipeline build

    # Query (requires ANTHROPIC_API_KEY for LLM extraction)
    python -m src.pipeline query --product-type "novel food" --query "insect protein labelling"
"""

import argparse
import json
import sys
import time
import warnings
from dataclasses import asdict
from pathlib import Path

from bs4 import XMLParsedAsHTMLWarning

from src.extraction.entity_extractor import (
    CrossReference,
    DefinedTerm,
    EntityIndex,
    extract_entities,
)
from src.extraction.llm_extractor import extract_requirements
from src.extraction.schemas import ExtractionResult
from src.indexing.vector_store import VectorStore
from src.ingestion.html_parser import parse_corpus
from src.retrieval.chunking import chunk_corpus
from src.retrieval.routing import RoutingTable

# Suppress BeautifulSoup warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

INDEX_DIR = Path("data/indexes")
VECTORSTORE_DIR = Path("data/vectorstore")


# --- Serialization ---


def save_entity_index(entity_index: EntityIndex, index_dir: Path = INDEX_DIR) -> None:
    """Serialize the entity index (defined terms + cross-references) to JSON."""
    index_dir.mkdir(parents=True, exist_ok=True)

    terms_data = [asdict(t) for t in entity_index.defined_terms]
    with open(index_dir / "defined_terms.json", "w") as f:
        json.dump(terms_data, f, indent=2, ensure_ascii=False)

    refs_data = [asdict(r) for r in entity_index.cross_references]
    with open(index_dir / "cross_references.json", "w") as f:
        json.dump(refs_data, f, indent=2, ensure_ascii=False)

    # Summary stats
    stats = {
        "total_defined_terms": len(entity_index.defined_terms),
        "unique_terms": len(entity_index.unique_terms),
        "total_cross_references": len(entity_index.cross_references),
        "regulations_with_terms": len(entity_index.celex_to_terms),
    }
    with open(index_dir / "entity_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"  Saved {len(terms_data)} defined terms → {index_dir / 'defined_terms.json'}")
    print(f"  Saved {len(refs_data)} cross-references → {index_dir / 'cross_references.json'}")


def load_entity_index(index_dir: Path = INDEX_DIR) -> EntityIndex:
    """Load the entity index from JSON."""
    terms_path = index_dir / "defined_terms.json"
    refs_path = index_dir / "cross_references.json"

    if not terms_path.exists() or not refs_path.exists():
        raise FileNotFoundError(
            f"Entity index not found in {index_dir}. Run 'python -m src.pipeline build' first."
        )

    with open(terms_path) as f:
        terms_data = json.load(f)
    defined_terms = [DefinedTerm(**t) for t in terms_data]

    with open(refs_path) as f:
        refs_data = json.load(f)
    cross_references = [CrossReference(**r) for r in refs_data]

    return EntityIndex(
        defined_terms=defined_terms,
        cross_references=cross_references,
    )


# --- Build Phase ---


def build_indexes(vectorstore_dir: Path = VECTORSTORE_DIR, index_dir: Path = INDEX_DIR) -> dict:
    """Run the full offline build phase.

    Parses the corpus, chunks articles, extracts entities, builds the vector store,
    and serializes everything to disk.

    Returns:
        Summary dict with counts and timing.
    """
    summary: dict = {}
    t0 = time.time()

    # Step 1: Parse corpus
    print("Step 1/4: Parsing HTML corpus...")
    regulations = parse_corpus()
    n_articles = sum(len(r.articles) for r in regulations)
    summary["regulations"] = len(regulations)
    summary["articles"] = n_articles
    print(f"  Parsed {len(regulations)} regulations, {n_articles} articles")

    # Step 2: Chunk articles
    print("Step 2/4: Chunking articles...")
    chunks = chunk_corpus(regulations)
    summary["chunks"] = len(chunks)
    print(f"  Created {len(chunks)} chunks")

    # Step 3: Extract entities
    print("Step 3/4: Extracting entities...")
    entity_index = extract_entities(regulations)
    summary["defined_terms"] = len(entity_index.defined_terms)
    summary["unique_terms"] = len(entity_index.unique_terms)
    summary["cross_references"] = len(entity_index.cross_references)
    print(f"  Found {len(entity_index.defined_terms)} defined terms "
          f"({len(entity_index.unique_terms)} unique), "
          f"{len(entity_index.cross_references)} cross-references")

    # Save entity index
    save_entity_index(entity_index, index_dir)

    # Step 4: Build vector store
    print("Step 4/4: Building vector store (embedding chunks)...")
    store = VectorStore(persist_dir=vectorstore_dir)
    store.delete_all()
    n_indexed = store.index_chunks(chunks)
    summary["indexed_chunks"] = n_indexed
    print(f"  Indexed {n_indexed} chunks in vector store")

    elapsed = time.time() - t0
    summary["build_time_seconds"] = round(elapsed, 1)
    print(f"\nBuild complete in {elapsed:.1f}s")

    # Save build summary
    index_dir.mkdir(parents=True, exist_ok=True)
    with open(index_dir / "build_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary


# --- Query Phase ---


def query(
    product_type: str = "",
    ingredients: list[str] | None = None,
    claims: list[str] | None = None,
    packaging: str = "",
    keywords: list[str] | None = None,
    query_text: str = "",
    n_results: int = 10,
    provider: str = "anthropic",
    api_key: str | None = None,
    model: str | None = None,
    skip_extraction: bool = False,
    vectorstore_dir: Path = VECTORSTORE_DIR,
    index_dir: Path = INDEX_DIR,
) -> dict:
    """Run a query through the full pipeline.

    Args:
        product_type: Product category (e.g. "novel food", "food supplement").
        ingredients: Ingredient keywords (e.g. ["food additive", "vitamin"]).
        claims: Claim types (e.g. ["health claim"]).
        packaging: Packaging type (e.g. "plastic packaging").
        keywords: Additional routing keywords (e.g. ["gmo"]).
        query_text: Natural language query for vector search.
        n_results: Number of articles to retrieve.
        provider: LLM provider — "anthropic", "openai", or "claude-code".
        api_key: API key (for anthropic/openai). Falls back to env var.
        model: Model to use. None means use provider default.
        skip_extraction: If True, skip LLM extraction (return retrieved articles only).
        vectorstore_dir: Path to the vector store directory.
        index_dir: Path to the entity index directory.

    Returns:
        Dict with routing results, retrieved articles, and (optionally) extracted requirements.
    """
    # Load indexes
    entity_index = load_entity_index(index_dir)
    routing_table = RoutingTable(entity_index)
    store = VectorStore(persist_dir=vectorstore_dir)

    if store.count == 0:
        raise RuntimeError(
            "Vector store is empty. Run 'python -m src.pipeline build' first."
        )

    # Step 1: Route to relevant regulations
    routing_result = routing_table.route(
        product_type=product_type,
        ingredients=ingredients,
        claims=claims,
        packaging=packaging,
        keywords=keywords,
    )

    # Step 2: Semantic search within routed regulations
    if not query_text:
        # Build query from the input parameters
        parts = []
        if product_type:
            parts.append(product_type)
        if ingredients:
            parts.extend(ingredients)
        if claims:
            parts.extend(claims)
        if packaging:
            parts.append(packaging)
        if keywords:
            parts.extend(keywords)
        query_text = " ".join(parts) if parts else "food safety requirements"

    # Hybrid search: first run a broad query to get the most semantically
    # relevant results, then add per-regulation results to ensure coverage
    # of every routed regulation.
    search_results = store.search(
        query=query_text,
        celex_ids=routing_result.celex_ids,
        n_results=n_results,
    )

    seen_chunk_ids = {r["chunk_id"] for r in search_results}
    covered_celex = {r["metadata"]["celex_id"] for r in search_results}
    per_reg = max(2, n_results // len(routing_result.celex_ids)) if routing_result.celex_ids else 0

    for celex_id in routing_result.celex_ids:
        hits = store.search(
            query=query_text,
            celex_ids=[celex_id],
            n_results=per_reg,
        )
        for hit in hits:
            if hit["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(hit["chunk_id"])
                search_results.append(hit)

    # Sort merged results by score descending
    search_results.sort(key=lambda x: x["score"], reverse=True)

    output = {
        "routing": {
            "celex_ids": routing_result.celex_ids,
            "reasons": routing_result.reasons,
            "regulation_count": len(routing_result.celex_ids),
        },
        "retrieval": {
            "query": query_text,
            "results_count": len(search_results),
            "articles": search_results,
        },
    }

    # Step 3: LLM extraction (optional)
    if not skip_extraction and search_results:
        product_desc = product_type or "food product"
        if ingredients:
            product_desc += f" with {', '.join(ingredients)}"

        extraction_result = extract_requirements(
            articles=search_results,
            product_context=product_desc,
            provider=provider,
            api_key=api_key,
            model=model,
        )

        output["extraction"] = {
            "requirements": [r.model_dump() for r in extraction_result.requirements],
            "requirements_count": len(extraction_result.requirements),
            "articles_processed": extraction_result.articles_processed,
        }
    elif skip_extraction:
        output["extraction"] = {"skipped": True}

    return output


# --- CLI ---


def _cli_build(args: argparse.Namespace) -> None:
    """Handle 'build' subcommand."""
    summary = build_indexes()
    print(f"\nSummary: {json.dumps(summary, indent=2)}")


def _cli_query(args: argparse.Namespace) -> None:
    """Handle 'query' subcommand."""
    result = query(
        product_type=args.product_type or "",
        ingredients=args.ingredients,
        claims=args.claims,
        packaging=args.packaging or "",
        keywords=args.keywords,
        query_text=args.query or "",
        n_results=args.n_results,
        provider=args.provider,
        model=args.model,
        skip_extraction=args.skip_extraction,
    )

    # Print routing
    routing = result["routing"]
    print(f"\nRouting: {routing['regulation_count']} regulations")
    for celex, reasons in routing["reasons"].items():
        print(f"  {celex}: {', '.join(reasons)}")

    # Print retrieval
    retrieval = result["retrieval"]
    print(f"\nRetrieved {retrieval['results_count']} articles for: \"{retrieval['query']}\"")
    for i, article in enumerate(retrieval["articles"], 1):
        meta = article["metadata"]
        print(f"  {i}. [{meta.get('celex_id', '?')}] Art. {meta.get('article_number', '?')} "
              f"— {meta.get('article_title', '?')} (score: {article['score']:.3f})")

    # Print extraction
    if "extraction" in result and not result["extraction"].get("skipped"):
        extraction = result["extraction"]
        print(f"\nExtracted {extraction['requirements_count']} requirements:")
        for i, req in enumerate(extraction["requirements"], 1):
            print(f"  {i}. [{req['priority']}] {req['requirement_summary']}")
            print(f"     Type: {req['requirement_type']}, Confidence: {req['confidence']}")
            print(f"     Source: {req['regulation_id']} Art. {req['article_number']}")
    elif result.get("extraction", {}).get("skipped"):
        print("\nLLM extraction skipped (use without --skip-extraction to enable)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.pipeline",
        description="EU Food Safety Regulatory Intelligence Pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Build command
    subparsers.add_parser("build", help="Build offline indexes from the downloaded corpus")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the pipeline")
    query_parser.add_argument("--product-type", type=str, help="Product category")
    query_parser.add_argument("--ingredients", nargs="+", help="Ingredient keywords")
    query_parser.add_argument("--claims", nargs="+", help="Claim types")
    query_parser.add_argument("--packaging", type=str, help="Packaging type")
    query_parser.add_argument("--keywords", nargs="+", help="Additional routing keywords")
    query_parser.add_argument("--query", type=str, help="Natural language query for search")
    query_parser.add_argument("--n-results", type=int, default=10, help="Number of articles to retrieve")
    query_parser.add_argument("--provider", type=str, default="anthropic",
                              choices=["anthropic", "openai", "claude-code"],
                              help="LLM provider (default: anthropic)")
    query_parser.add_argument("--model", type=str, default=None,
                              help="Model override (default: provider's default)")
    query_parser.add_argument("--skip-extraction", action="store_true",
                              help="Skip LLM extraction (routing + retrieval only)")

    args = parser.parse_args()

    if args.command == "build":
        _cli_build(args)
    elif args.command == "query":
        _cli_query(args)


if __name__ == "__main__":
    main()
