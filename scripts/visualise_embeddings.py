"""
Generate publication-quality visualizations of the vector store embeddings.

Standalone script for blog post illustrations — not part of the pipeline.
Reads from the already-built data/vectorstore/ and data/indexes/ directories.

Usage:
    pip install -e ".[viz]"
    python -m scripts.visualise_embeddings --all
    python -m scripts.visualise_embeddings --umap --distribution
    python -m scripts.visualise_embeddings --query --query-text "novel food insect protein"
"""

import argparse
import json
import warnings
from pathlib import Path

import numpy as np

from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

VECTORSTORE_DIR = Path("data/vectorstore")
INDEX_DIR = Path("data/indexes")
OUTPUT_DIR = Path("visuals")

# UMAP hyperparameters
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
UMAP_METRIC = "cosine"
UMAP_RANDOM_STATE = 42


def load_data() -> dict:
    """Load embeddings, metadata, corpus, and cross-references."""
    from src.ingestion.corpus import CATEGORIES, CORPUS

    # Load embeddings
    embeddings = np.load(VECTORSTORE_DIR / "embeddings.npy")

    # Load metadata
    with open(VECTORSTORE_DIR / "metadata.json") as f:
        meta = json.load(f)

    # Load cross-references
    with open(INDEX_DIR / "cross_references.json") as f:
        cross_refs = json.load(f)

    # Map each chunk to its category
    metadatas = meta["metadatas"]
    categories = []
    for m in metadatas:
        celex = m.get("celex_id", "")
        entry = CORPUS.get(celex, {})
        categories.append(entry.get("category", "unknown"))

    return {
        "embeddings": embeddings,
        "ids": meta["ids"],
        "metadatas": metadatas,
        "categories": categories,
        "corpus": CORPUS,
        "category_labels": CATEGORIES,
        "cross_refs": cross_refs,
    }


def setup_style() -> None:
    """Set matplotlib rcParams for publication quality."""
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def build_category_colormap(categories: list[str], category_labels: dict) -> dict:
    """Assign colors to categories, muting official_controls."""
    import matplotlib.pyplot as plt

    # Count chunks per category and sort descending
    from collections import Counter
    counts = Counter(categories)
    sorted_cats = sorted(counts.keys(), key=lambda c: counts[c], reverse=True)

    # Get tab20 colors
    tab20 = plt.colormaps["tab20"]
    colormap = {}
    color_idx = 0
    for cat in sorted_cats:
        if cat == "official_controls":
            colormap[cat] = (0.78, 0.78, 0.78, 1.0)  # muted gray
        else:
            colormap[cat] = tab20(color_idx % 20)
            color_idx += 1

    return colormap


def compute_umap(embeddings: np.ndarray):
    """Run UMAP dimensionality reduction. Returns (coords_2d, umap_model)."""
    import umap

    print("  Computing UMAP projection (this may take 30-60 seconds)...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=UMAP_N_NEIGHBORS,
        min_dist=UMAP_MIN_DIST,
        metric=UMAP_METRIC,
        random_state=UMAP_RANDOM_STATE,
    )
    coords = reducer.fit_transform(embeddings)
    return coords, reducer


def plot_umap_scatter(data: dict, output_dir: Path, umap_result=None) -> Path:
    """UMAP scatter plot of all chunks, colored by regulation category."""
    import matplotlib.pyplot as plt

    if umap_result is None:
        coords, reducer = compute_umap(data["embeddings"])
    else:
        coords, reducer = umap_result

    colormap = build_category_colormap(data["categories"], data["category_labels"])
    categories = data["categories"]
    labels = data["category_labels"]

    # Count per category for legend
    from collections import Counter
    counts = Counter(categories)

    fig, ax = plt.subplots(figsize=(12, 8))

    # Plot each category separately for legend entries, sorted by count (largest last = on top for small ones)
    sorted_cats = sorted(counts.keys(), key=lambda c: counts[c], reverse=True)
    for cat in sorted_cats:
        mask = np.array([c == cat for c in categories])
        label_text = labels.get(cat, cat)
        ax.scatter(
            coords[mask, 0], coords[mask, 1],
            c=[colormap[cat]],
            s=8,
            alpha=0.6,
            label=f"{label_text} ({counts[cat]})",
            rasterized=True,
        )

    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    ax.set_title(
        f"EU Food Safety Regulation Embeddings\n"
        f"{len(categories):,} chunks across {len(counts)} categories",
        fontsize=13,
    )

    # Legend outside plot
    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=8,
        frameon=False,
        markerscale=2,
    )

    out_path = output_dir / "umap_scatter.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved {out_path}")
    return out_path


def plot_crossref_network(data: dict, output_dir: Path) -> Path:
    """Cross-reference network graph between regulations."""
    import matplotlib.pyplot as plt
    import networkx as nx

    from src.ingestion.corpus import CORPUS
    from src.retrieval.cross_references import regulation_number_to_celex

    corpus_celex_ids = set(CORPUS.keys())

    # Build directed graph
    G = nx.DiGraph()
    for ref in data["cross_refs"]:
        source = ref["source_celex"]
        target_celex = regulation_number_to_celex(
            ref["target_regulation_number"], corpus_celex_ids
        )
        if target_celex and target_celex != source:
            if not G.has_edge(source, target_celex):
                G.add_edge(source, target_celex)

    # Add category attributes
    labels = data["category_labels"]
    colormap = build_category_colormap(
        [CORPUS.get(n, {}).get("category", "unknown") for n in G.nodes()],
        labels,
    )

    node_colors = []
    for n in G.nodes():
        cat = CORPUS.get(n, {}).get("category", "unknown")
        node_colors.append(colormap.get(cat, (0.5, 0.5, 0.5, 1.0)))

    # Node size by in-degree
    in_degrees = dict(G.in_degree())
    node_sizes = [100 + in_degrees.get(n, 0) * 40 for n in G.nodes()]

    fig, ax = plt.subplots(figsize=(14, 10))

    pos = nx.kamada_kawai_layout(G)

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        alpha=0.12, width=0.5,
        arrows=True, arrowsize=6,
        edge_color="#666666",
    )

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.85,
        linewidths=0.3,
        edgecolors="white",
    )

    # Short names for the most important hub regulations
    SHORT_NAMES = {
        "32002R0178": "General Food Law",
        "32004R0852": "Food Hygiene",
        "32004R0853": "Hygiene (Animal Origin)",
        "32017R0625": "Official Controls",
        "32011R1169": "Food Info (FIC)",
        "32008R1333": "Food Additives",
        "32008R1334": "Flavourings",
        "32008R1332": "Food Enzymes",
        "32008R1331": "Common Authorisation",
        "32015R2283": "Novel Foods",
        "32006R1924": "Health Claims",
        "32004R1935": "Food Contact Materials",
        "32003R1829": "GM Food & Feed",
        "32018R0848": "Organic Production",
        "32023R0915": "Contaminants",
        "32013R0609": "Food for Specific Groups",
    }

    # Label high-degree nodes
    top_nodes = sorted(G.nodes(), key=lambda n: in_degrees.get(n, 0), reverse=True)[:10]
    node_labels = {}
    for n in top_nodes:
        if n in SHORT_NAMES:
            node_labels[n] = SHORT_NAMES[n]
        else:
            title = CORPUS.get(n, {}).get("title", n)
            if len(title) > 30:
                title = title[:27] + "..."
            node_labels[n] = title

    nx.draw_networkx_labels(
        G, pos, labels=node_labels, ax=ax,
        font_size=7, font_weight="bold",
    )

    ax.set_title(
        f"Cross-Reference Network\n"
        f"{G.number_of_nodes()} regulations, {G.number_of_edges()} directed references",
        fontsize=13,
    )
    ax.axis("off")

    # Category legend
    seen_cats = set()
    legend_handles = []
    for n in sorted(G.nodes(), key=lambda n: in_degrees.get(n, 0), reverse=True):
        cat = CORPUS.get(n, {}).get("category", "unknown")
        if cat not in seen_cats:
            seen_cats.add(cat)
            legend_handles.append(
                plt.Line2D([0], [0], marker="o", color="w",
                           markerfacecolor=colormap.get(cat, (0.5, 0.5, 0.5, 1.0)),
                           markersize=8, label=labels.get(cat, cat))
            )
    ax.legend(handles=legend_handles, bbox_to_anchor=(1.02, 1), loc="upper left",
              fontsize=7, frameon=False)

    out_path = output_dir / "crossref_network.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved {out_path}")
    return out_path


def plot_query_retrieval(
    data: dict, output_dir: Path, umap_result, query_text: str, product_type: str
) -> Path:
    """Show a query projected into the UMAP space with nearest neighbors highlighted."""
    import matplotlib.pyplot as plt

    from src.indexing.vector_store import VectorStore

    coords, reducer = umap_result

    # Run a search
    store = VectorStore()
    results = store.search(query=query_text, n_results=10)

    if not results:
        print("  WARNING: No search results for query, skipping query visualization")
        return output_dir / "query_retrieval.png"

    # Find which indices in our data correspond to the results
    id_to_idx = {id_: i for i, id_ in enumerate(data["ids"])}
    result_indices = []
    for r in results:
        idx = id_to_idx.get(r["chunk_id"])
        if idx is not None:
            result_indices.append(idx)

    # Project query into UMAP space
    model = store._get_model()
    query_embedding = model.encode([query_text], normalize_embeddings=True)
    query_2d = reducer.transform(query_embedding)[0]

    fig, ax = plt.subplots(figsize=(12, 8))

    # All points in light gray
    ax.scatter(
        coords[:, 0], coords[:, 1],
        c="#DDDDDD", s=6, alpha=0.3,
        rasterized=True,
    )

    # Highlight results
    for idx in result_indices:
        ax.plot(
            [query_2d[0], coords[idx, 0]],
            [query_2d[1], coords[idx, 1]],
            color="#FF4444", alpha=0.3, linewidth=0.8,
        )

    result_coords = coords[result_indices]
    ax.scatter(
        result_coords[:, 0], result_coords[:, 1],
        c="#FF4444", s=40, alpha=0.8,
        edgecolors="white", linewidths=0.5,
        label=f"Top {len(result_indices)} results",
        zorder=5,
    )

    # Query point
    ax.scatter(
        [query_2d[0]], [query_2d[1]],
        c="#FFD700", s=200, marker="*",
        edgecolors="black", linewidths=0.8,
        label="Query",
        zorder=6,
    )

    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")

    display_query = query_text if len(query_text) <= 50 else query_text[:47] + "..."
    ax.set_title(
        f"Semantic Retrieval Example\n"
        f"Query: \"{display_query}\"",
        fontsize=13,
    )
    ax.legend(loc="upper right", fontsize=9)

    out_path = output_dir / "query_retrieval.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved {out_path}")
    return out_path


def plot_chunk_distribution(data: dict, output_dir: Path) -> Path:
    """Horizontal bar chart of chunks per category."""
    import matplotlib.pyplot as plt
    from collections import Counter

    counts = Counter(data["categories"])
    labels = data["category_labels"]
    colormap = build_category_colormap(data["categories"], labels)

    # Sort ascending (so largest is at top in horizontal bar chart)
    sorted_cats = sorted(counts.keys(), key=lambda c: counts[c])

    cat_labels = [labels.get(c, c) for c in sorted_cats]
    cat_counts = [counts[c] for c in sorted_cats]
    cat_colors = [colormap[c] for c in sorted_cats]

    fig, ax = plt.subplots(figsize=(10, 7))

    bars = ax.barh(cat_labels, cat_counts, color=cat_colors, edgecolor="white", linewidth=0.5)

    # Annotate counts
    for bar, count in zip(bars, cat_counts):
        ax.text(
            bar.get_width() + 15, bar.get_y() + bar.get_height() / 2,
            str(count),
            va="center", fontsize=9,
        )

    ax.set_xlabel("Number of chunks")
    ax.set_title(
        f"Chunk Distribution by Regulation Category\n"
        f"{sum(cat_counts):,} total chunks across {len(counts)} categories",
        fontsize=13,
    )
    ax.set_xlim(0, max(cat_counts) * 1.12)

    out_path = output_dir / "chunk_distribution.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate embedding visualizations for blog post illustrations"
    )
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR))
    parser.add_argument("--all", action="store_true", help="Generate all visualizations")
    parser.add_argument("--umap", action="store_true", help="UMAP scatter plot")
    parser.add_argument("--network", action="store_true", help="Cross-reference network")
    parser.add_argument("--query", action="store_true", help="Query retrieval example")
    parser.add_argument("--distribution", action="store_true", help="Chunk distribution bar chart")
    parser.add_argument("--query-text", type=str, default="novel food insect protein labelling requirements")
    parser.add_argument("--product-type", type=str, default="novel food")
    args = parser.parse_args()

    # Default to --all if nothing specified
    if not any([args.all, args.umap, args.network, args.query, args.distribution]):
        args.all = True

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    data = load_data()
    print(f"  {len(data['embeddings'])} embeddings, {len(set(data['categories']))} categories")

    setup_style()

    # Compute UMAP once if needed by multiple plots
    umap_result = None
    needs_umap = args.all or args.umap or args.query
    if needs_umap:
        umap_result = compute_umap(data["embeddings"])

    if args.all or args.umap:
        print("\nGenerating UMAP scatter plot...")
        plot_umap_scatter(data, output_dir, umap_result)

    if args.all or args.network:
        print("\nGenerating cross-reference network...")
        plot_crossref_network(data, output_dir)

    if args.all or args.query:
        print("\nGenerating query retrieval example...")
        plot_query_retrieval(
            data, output_dir, umap_result,
            query_text=args.query_text,
            product_type=args.product_type,
        )

    if args.all or args.distribution:
        print("\nGenerating chunk distribution chart...")
        plot_chunk_distribution(data, output_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
