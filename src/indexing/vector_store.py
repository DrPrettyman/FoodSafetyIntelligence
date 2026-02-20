"""
Vector store for article chunks using sentence-transformers + numpy.

Indexes ArticleChunks with metadata for filtered retrieval. The routing table
narrows the search space to relevant regulations, and the vector store
provides semantic similarity search within that subset.

Uses all-MiniLM-L6-v2 for embeddings — runs locally, no API key needed.
Persistence via numpy .npz files + JSON metadata.
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from src.retrieval.chunking import ArticleChunk

MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_PERSIST_DIR = "data/vectorstore"


class VectorStore:
    """Semantic search over article chunks with metadata filtering."""

    def __init__(self, persist_dir: str | Path = DEFAULT_PERSIST_DIR):
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._model: SentenceTransformer | None = None

        # In-memory index
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict] = []
        self._embeddings: np.ndarray | None = None

        # Try to load from disk
        self._load()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    @property
    def count(self) -> int:
        return len(self._ids)

    def index_chunks(self, chunks: list[ArticleChunk], batch_size: int = 256) -> int:
        """Embed and index chunks.

        Uses text_with_context (includes context header) for embedding.
        Stores full metadata for filtering.

        Returns the number of chunks indexed.
        """
        if not chunks:
            return 0

        model = self._get_model()
        texts = [c.text_with_context for c in chunks]

        # Encode in batches
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,  # pre-normalize for cosine similarity via dot product
        )

        self._ids = [c.chunk_id for c in chunks]
        self._texts = texts
        self._metadatas = [c.metadata for c in chunks]
        self._embeddings = np.array(embeddings, dtype=np.float32)

        self._save()
        return len(chunks)

    def search(
        self,
        query: str,
        celex_ids: list[str] | None = None,
        n_results: int = 10,
    ) -> list[dict]:
        """Search for chunks similar to the query.

        Args:
            query: Natural language query text.
            celex_ids: If provided, restrict search to these regulations only.
            n_results: Number of results to return.

        Returns:
            List of dicts with keys: chunk_id, text, metadata, score.
        """
        if self._embeddings is None or len(self._ids) == 0:
            return []

        model = self._get_model()
        query_embedding = model.encode(
            [query], normalize_embeddings=True
        )[0]

        # Build mask for celex_id filtering
        if celex_ids:
            celex_set = set(celex_ids)
            mask = np.array(
                [m.get("celex_id", "") in celex_set for m in self._metadatas],
                dtype=bool,
            )
            if not mask.any():
                return []
        else:
            mask = np.ones(len(self._ids), dtype=bool)

        # Cosine similarity = dot product (embeddings are pre-normalized)
        scores = self._embeddings @ query_embedding

        # Apply mask: set non-matching scores to -inf
        scores[~mask] = -np.inf

        # Get top-k indices
        k = min(n_results, int(mask.sum()))
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        output = []
        for idx in top_indices:
            if scores[idx] == -np.inf:
                continue
            output.append(
                {
                    "chunk_id": self._ids[idx],
                    "text": self._texts[idx],
                    "metadata": self._metadatas[idx],
                    "score": float(scores[idx]),
                }
            )

        return output

    def _save(self) -> None:
        """Persist index to disk."""
        if self._embeddings is None:
            return

        np.save(self._persist_dir / "embeddings.npy", self._embeddings)

        meta = {
            "ids": self._ids,
            "metadatas": self._metadatas,
        }
        with open(self._persist_dir / "metadata.json", "w") as f:
            json.dump(meta, f)

        # Save texts separately (can be large)
        with open(self._persist_dir / "texts.json", "w") as f:
            json.dump(self._texts, f)

    def _load(self) -> None:
        """Load index from disk if available."""
        emb_path = self._persist_dir / "embeddings.npy"
        meta_path = self._persist_dir / "metadata.json"
        texts_path = self._persist_dir / "texts.json"

        if not (emb_path.exists() and meta_path.exists() and texts_path.exists()):
            return

        self._embeddings = np.load(emb_path)

        with open(meta_path) as f:
            meta = json.load(f)
        self._ids = meta["ids"]
        self._metadatas = meta["metadatas"]

        with open(texts_path) as f:
            self._texts = json.load(f)

    def delete_all(self) -> None:
        """Remove all data."""
        self._ids = []
        self._texts = []
        self._metadatas = []
        self._embeddings = None

        for fname in ["embeddings.npy", "metadata.json", "texts.json"]:
            path = self._persist_dir / fname
            if path.exists():
                path.unlink()
