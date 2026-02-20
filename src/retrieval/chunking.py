"""
Article-aware chunking for EU regulatory text.

Each article becomes a chunk. Long articles are sub-chunked at paragraph
boundaries with parent context (article number, title, chapter) preserved
in every sub-chunk. This is critical because:
- An article is the atomic unit of a legal obligation
- Cross-references point to specific articles
- Retrieving half an article can be misleading

Each chunk carries metadata for vector store filtering:
celex_id, article_number, chapter, section, chunk_index, char_count.
"""

from dataclasses import dataclass, field

from src.ingestion.html_parser import Article, ParsedRegulation

# Articles longer than this get sub-chunked at paragraph boundaries
MAX_CHUNK_CHARS = 2000

# When sub-chunking, aim for chunks of at least this size
MIN_CHUNK_CHARS = 200


@dataclass
class ArticleChunk:
    celex_id: str
    article_number: int
    article_title: str
    text: str
    chapter: str = ""
    section: str = ""
    chunk_index: int = 0  # 0 = whole article or first sub-chunk
    total_chunks: int = 1
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)

    @property
    def chunk_id(self) -> str:
        """Unique identifier for this chunk."""
        base = f"{self.celex_id}_art{self.article_number}"
        # Occurrence suffix for duplicate article numbers (amending regulations)
        occ = getattr(self, "_occurrence", 0)
        if occ > 0:
            base += f"_occ{occ}"
        if self.total_chunks == 1:
            return base
        return f"{base}_chunk{self.chunk_index}"

    @property
    def context_header(self) -> str:
        """Human-readable context prefix for the chunk."""
        parts = [f"[{self.celex_id}]"]
        if self.chapter:
            parts.append(self.chapter)
        if self.section:
            parts.append(self.section)
        parts.append(f"Article {self.article_number}")
        if self.article_title:
            parts.append(f"— {self.article_title}")
        if self.total_chunks > 1:
            parts.append(f"(part {self.chunk_index + 1}/{self.total_chunks})")
        return " ".join(parts)

    @property
    def text_with_context(self) -> str:
        """Text prefixed with context header — use this for embedding."""
        return f"{self.context_header}\n\n{self.text}"

    @property
    def metadata(self) -> dict:
        """Metadata dict for vector store."""
        return {
            "celex_id": self.celex_id,
            "article_number": self.article_number,
            "article_title": self.article_title,
            "chapter": self.chapter,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "chunk_id": self.chunk_id,
            "char_count": self.char_count,
        }


def chunk_article(article: Article, max_chars: int = MAX_CHUNK_CHARS) -> list[ArticleChunk]:
    """Split an article into one or more chunks.

    Short articles (<= max_chars) become a single chunk.
    Long articles are split at paragraph boundaries (newlines).
    """
    if not article.text.strip():
        return [
            ArticleChunk(
                celex_id=article.celex_id,
                article_number=article.article_number,
                article_title=article.title,
                text=article.title or "(empty article)",
                chapter=article.chapter,
                section=article.section,
            )
        ]

    if len(article.text) <= max_chars:
        return [
            ArticleChunk(
                celex_id=article.celex_id,
                article_number=article.article_number,
                article_title=article.title,
                text=article.text,
                chapter=article.chapter,
                section=article.section,
            )
        ]

    # Sub-chunk at paragraph boundaries
    paragraphs = article.text.split("\n")
    chunks_text: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if current_len + len(para) > max_chars and current_len >= MIN_CHUNK_CHARS:
            chunks_text.append("\n".join(current_parts))
            current_parts = [para]
            current_len = len(para)
        else:
            current_parts.append(para)
            current_len += len(para)

    if current_parts:
        # If the last chunk is too small, merge with previous
        if len(chunks_text) > 0 and current_len < MIN_CHUNK_CHARS:
            chunks_text[-1] += "\n" + "\n".join(current_parts)
        else:
            chunks_text.append("\n".join(current_parts))

    total = len(chunks_text)
    return [
        ArticleChunk(
            celex_id=article.celex_id,
            article_number=article.article_number,
            article_title=article.title,
            text=text,
            chapter=article.chapter,
            section=article.section,
            chunk_index=i,
            total_chunks=total,
        )
        for i, text in enumerate(chunks_text)
    ]


def chunk_regulation(regulation: ParsedRegulation, max_chars: int = MAX_CHUNK_CHARS) -> list[ArticleChunk]:
    """Chunk all articles in a regulation.

    Amending regulations can contain multiple articles with the same number
    (e.g. inserting Art 8, 8a, 8b into a target regulation). When duplicate
    article numbers are detected, an occurrence suffix is appended to keep
    chunk IDs unique.
    """
    chunks = []
    for article in regulation.articles:
        chunks.extend(chunk_article(article, max_chars))

    # Deduplicate chunk IDs: track occurrences and rename duplicates
    seen: dict[str, int] = {}
    for chunk in chunks:
        cid = chunk.chunk_id
        if cid in seen:
            seen[cid] += 1
        else:
            seen[cid] = 1

    # Only process if there are actual duplicates
    has_dupes = any(v > 1 for v in seen.values())
    if has_dupes:
        counters: dict[str, int] = {}
        for chunk in chunks:
            cid = chunk.chunk_id
            if seen[cid] > 1:
                counters[cid] = counters.get(cid, 0) + 1
                chunk._occurrence = counters[cid]
            else:
                chunk._occurrence = 0

    return chunks


def chunk_corpus(regulations: list[ParsedRegulation], max_chars: int = MAX_CHUNK_CHARS) -> list[ArticleChunk]:
    """Chunk all regulations in the corpus."""
    chunks = []
    for regulation in regulations:
        chunks.extend(chunk_regulation(regulation, max_chars))
    return chunks
