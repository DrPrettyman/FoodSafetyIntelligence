"""
Extract defined terms and cross-references from EU food safety regulations.

Defined terms are extracted from Definitions articles using regex patterns
that match the standard EU legislative drafting conventions:
  - 'term' means / shall mean ...
  - "term" means / shall mean ...
  - (letter-prefixed or number-prefixed definitions)

Cross-references to other regulations are extracted from all articles:
  - Regulation (EC) No 178/2002
  - Directive 2001/18/EC
  - Commission Regulation (EU) 2015/2283

These form the basis of the routing table: term → regulation + article.
"""

import re
from dataclasses import dataclass, field

from src.ingestion.corpus import CORPUS
from src.ingestion.html_parser import Article, ParsedRegulation

# Regex for quoted terms followed by "means" / "shall mean" / "is defined as"
# Handles: 'term', "term", "term", «term»
_TERM_PATTERN = re.compile(
    r"""
    [\u2018\u2019'"\u201c\u201d\u00ab\u00bb]  # opening quote
    \s*
    ([^'"\u2018\u2019\u201c\u201d\u00ab\u00bb]{2,80})  # term text (2-80 chars)
    \s*
    [\u2018\u2019'"\u201c\u201d\u00ab\u00bb]  # closing quote
    \s*
    (?:\([^)]{0,80}\)\s*)?                   # optional parenthetical, e.g. (or "foodstuff")
    (?:,\s*hereinafter\s+(?:called|referred\s+to\s+as)\s*[\u2018\u2019'"\u201c\u201d\u00ab\u00bb]\s*
    [^'"\u2018\u2019\u201c\u201d\u00ab\u00bb]+\s*
    [\u2018\u2019'"\u201c\u201d\u00ab\u00bb]\s*,?\s*)?  # optional "hereinafter called 'X'"
    (?:shall\s+)?mean[s]?                    # "means" or "shall mean"
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Pattern for cross-references to other EU legislation
# Matches: Regulation (EC) No 178/2002, Directive 2001/18/EC, etc.
_CELEX_REF_PATTERN = re.compile(
    r"""
    (?:Commission\s+|European\s+Parliament\s+(?:and\s+(?:of\s+the\s+)?Council\s+)?)?
    (?:Regulation|Directive|Decision)
    \s*
    \((?:EC|EU|EEC|Euratom)\)
    \s*
    (?:No\s+)?
    (\d{1,4})/(\d{4})   # number/year
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class DefinedTerm:
    """A term defined in a Definitions article."""

    term: str  # normalized term text, e.g. "food additive"
    celex_id: str
    article_number: int
    definition_snippet: str  # first ~200 chars of the definition
    category: str = ""  # from corpus.py

    @property
    def term_lower(self) -> str:
        return self.term.lower().strip()


@dataclass
class CrossReference:
    """A reference from one regulation to another."""

    source_celex: str
    source_article: int
    target_regulation_number: str  # e.g. "178/2002"
    context: str  # surrounding text snippet


@dataclass
class EntityIndex:
    """Aggregated index of all extracted entities from the corpus."""

    defined_terms: list[DefinedTerm] = field(default_factory=list)
    cross_references: list[CrossReference] = field(default_factory=list)

    @property
    def term_to_sources(self) -> dict[str, list[DefinedTerm]]:
        """Map normalized term → list of defining sources."""
        result: dict[str, list[DefinedTerm]] = {}
        for dt in self.defined_terms:
            key = dt.term_lower
            if key not in result:
                result[key] = []
            result[key].append(dt)
        return result

    @property
    def celex_to_terms(self) -> dict[str, list[DefinedTerm]]:
        """Map celex_id → list of terms defined in that regulation."""
        result: dict[str, list[DefinedTerm]] = {}
        for dt in self.defined_terms:
            if dt.celex_id not in result:
                result[dt.celex_id] = []
            result[dt.celex_id].append(dt)
        return result

    @property
    def unique_terms(self) -> list[str]:
        """Sorted list of unique normalized terms."""
        return sorted(set(dt.term_lower for dt in self.defined_terms))


def _normalize_term(raw: str) -> str:
    """Clean up extracted term text."""
    # Remove leading/trailing whitespace and punctuation artifacts
    term = raw.strip()
    # Collapse internal whitespace
    term = re.sub(r"\s+", " ", term)
    # Remove trailing commas, semicolons
    term = term.rstrip(",;.")
    return term


def extract_defined_terms(article: Article) -> list[DefinedTerm]:
    """Extract defined terms from a single article (typically a Definitions article).

    Returns a list of DefinedTerm objects for each quoted-term-means pattern found.
    """
    text = article.text
    if not text:
        return []

    category = CORPUS.get(article.celex_id, {}).get("category", "")

    terms: list[DefinedTerm] = []
    seen_terms: set[str] = set()

    for match in _TERM_PATTERN.finditer(text):
        raw_term = match.group(1)
        term = _normalize_term(raw_term)

        if not term or len(term) < 2:
            continue

        term_lower = term.lower()
        if term_lower in seen_terms:
            continue
        seen_terms.add(term_lower)

        # Get definition snippet: text after the match, up to 200 chars
        start = match.end()
        snippet_end = min(start + 200, len(text))
        snippet = text[start:snippet_end].strip()
        # Truncate at sentence boundary if possible
        sentence_end = snippet.find(";")
        if sentence_end > 50:
            snippet = snippet[:sentence_end]

        terms.append(
            DefinedTerm(
                term=term,
                celex_id=article.celex_id,
                article_number=article.article_number,
                definition_snippet=snippet,
                category=category,
            )
        )

    return terms


def extract_cross_references(article: Article) -> list[CrossReference]:
    """Extract cross-references to other EU regulations from article text."""
    text = article.text
    if not text:
        return []

    refs: list[CrossReference] = []
    seen: set[str] = set()

    for match in _CELEX_REF_PATTERN.finditer(text):
        reg_number = f"{match.group(1)}/{match.group(2)}"

        if reg_number in seen:
            continue
        seen.add(reg_number)

        # Get context around the match
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 50)
        context = text[start:end]

        refs.append(
            CrossReference(
                source_celex=article.celex_id,
                source_article=article.article_number,
                target_regulation_number=reg_number,
                context=context,
            )
        )

    return refs


def extract_entities(regulations: list[ParsedRegulation]) -> EntityIndex:
    """Extract all defined terms and cross-references from the corpus.

    Scans Definitions articles for defined terms, and all articles for
    cross-references to other regulations.
    """
    index = EntityIndex()

    for reg in regulations:
        for article in reg.articles:
            # Extract defined terms from Definitions-like articles
            title_lower = article.title.lower()
            if "definition" in title_lower or "scope" in title_lower:
                terms = extract_defined_terms(article)
                index.defined_terms.extend(terms)

            # Extract cross-references from all articles
            refs = extract_cross_references(article)
            index.cross_references.extend(refs)

    return index
