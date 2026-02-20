"""
Parse EUR-Lex HTML/XHTML into structured article data.

Handles three format variants:
- Newer XHTML (post-~2013): CSS classes .oj-ti-art, .oj-sti-art, .eli-container
- Mid-era XHTML (~2004-2012): same classes without "oj-" prefix (.ti-art, .sti-art)
- Older HTML (pre-~2004): bare <p> tags inside <div id="TexteOnly"> / <TXT_TE>

Output: list of Article dicts, each with celex_id, article_number, title, text,
chapter, section.
"""

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass
class Article:
    celex_id: str
    article_number: int
    title: str  # e.g. "Subject matter and purpose"
    text: str  # plain text of the article body
    chapter: str = ""
    section: str = ""


@dataclass
class ParsedRegulation:
    celex_id: str
    title: str
    articles: list[Article] = field(default_factory=list)
    preamble_text: str = ""
    format_type: str = ""  # "xhtml" or "html_legacy"


def detect_format(soup: BeautifulSoup) -> str:
    """Detect whether this is newer XHTML, mid-era XHTML, or older HTML format."""
    if soup.find(class_="eli-container"):
        return "xhtml"
    if soup.find(class_="ti-art"):
        return "xhtml_mid"
    if soup.find("div", id="TexteOnly"):
        return "html_legacy"
    raise ValueError("Unknown EUR-Lex HTML format: no eli-container, ti-art, or TexteOnly div found")


def _parse_xhtml(soup: BeautifulSoup, celex_id: str) -> ParsedRegulation:
    """Parse newer XHTML format with ELI semantic markup."""
    # Extract document title
    title_parts = []
    for p in soup.find_all("p", class_="oj-doc-ti"):
        title_parts.append(p.get_text(strip=True))
    doc_title = " — ".join(title_parts) if title_parts else celex_id

    # Track current chapter/section context
    current_chapter = ""
    current_section = ""

    articles: list[Article] = []

    # Find all article heading elements
    art_headings = soup.find_all("p", class_="oj-ti-art")

    for heading in art_headings:
        heading_text = heading.get_text(strip=True)
        art_match = re.match(r"Article\s+(\d+)", heading_text)
        if not art_match:
            continue

        art_num = int(art_match.group(1))

        # Look for article subtitle (next sibling or child with oj-sti-art)
        art_title = ""
        # Check siblings of the heading's parent subdivision
        parent = heading.parent
        subtitle = parent.find("p", class_="oj-sti-art") if parent else None
        if subtitle:
            art_title = subtitle.get_text(strip=True)

        # Find the chapter/section context by walking up
        chapter, section = _find_chapter_section_xhtml(heading)
        if chapter:
            current_chapter = chapter
        if section:
            current_section = section

        # Collect article body text: all oj-normal paragraphs in the same subdivision
        body_parts = []
        if parent and parent.name == "div":
            for p in parent.find_all("p", class_="oj-normal"):
                text = p.get_text(strip=True)
                if text:
                    body_parts.append(text)

        article = Article(
            celex_id=celex_id,
            article_number=art_num,
            title=art_title,
            text="\n".join(body_parts),
            chapter=current_chapter,
            section=current_section,
        )
        articles.append(article)

    return ParsedRegulation(
        celex_id=celex_id,
        title=doc_title,
        articles=articles,
        format_type="xhtml",
    )


def _find_chapter_section_xhtml(element: Tag) -> tuple[str, str]:
    """Walk up from an article heading to find its chapter and section context."""
    chapter = ""
    section = ""

    current = element.parent
    while current:
        if isinstance(current, Tag):
            ch = current.find("p", class_="oj-ti-section-1")
            if ch and not chapter:
                chapter = ch.get_text(strip=True)
            sec = current.find("p", class_="oj-ti-section-2")
            if sec and not section:
                section = sec.get_text(strip=True)
        current = current.parent

    return chapter, section


def _parse_xhtml_mid(soup: BeautifulSoup, celex_id: str) -> ParsedRegulation:
    """Parse mid-era XHTML format (~2004-2012) with unprefixed class names.

    Same structure as newer XHTML but classes lack the 'oj-' prefix:
    ti-art, sti-art, normal, ti-section-1, ti-section-2, doc-ti.
    Articles are direct children of <body> rather than nested in eli-subdivision divs.
    """
    # Extract document title
    title_parts = []
    for p in soup.find_all("p", class_="doc-ti"):
        title_parts.append(p.get_text(strip=True))
    doc_title = " — ".join(title_parts) if title_parts else celex_id

    current_chapter = ""
    current_section = ""
    articles: list[Article] = []

    art_headings = soup.find_all("p", class_="ti-art")

    for heading in art_headings:
        heading_text = heading.get_text(strip=True)
        art_match = re.match(r"Article\s+(\d+)", heading_text)
        if not art_match:
            continue

        art_num = int(art_match.group(1))

        # Collect subtitle and body by walking next siblings
        art_title = ""
        body_parts = []

        sibling = heading.next_sibling
        while sibling:
            if isinstance(sibling, Tag):
                # Stop at next article heading or annex
                if "ti-art" in sibling.get("class", []):
                    break
                if "ti-section-1" in sibling.get("class", []):
                    current_chapter = sibling.get_text(strip=True)
                    sibling = sibling.next_sibling
                    continue
                if "ti-section-2" in sibling.get("class", []):
                    current_section = sibling.get_text(strip=True)
                    sibling = sibling.next_sibling
                    continue
                if "sti-art" in sibling.get("class", []):
                    art_title = sibling.get_text(strip=True)
                elif "normal" in sibling.get("class", []):
                    text = sibling.get_text(strip=True)
                    if text:
                        body_parts.append(text)
                elif sibling.name == "table":
                    # Tables within articles (e.g. numbered lists)
                    text = sibling.get_text(strip=True)
                    if text:
                        body_parts.append(text)
                elif "doc-sep" in sibling.get("class", []):
                    break
            sibling = sibling.next_sibling

        article = Article(
            celex_id=celex_id,
            article_number=art_num,
            title=art_title,
            text="\n".join(body_parts),
            chapter=current_chapter,
            section=current_section,
        )
        articles.append(article)

    return ParsedRegulation(
        celex_id=celex_id,
        title=doc_title,
        articles=articles,
        format_type="xhtml_mid",
    )


def _parse_html_legacy(soup: BeautifulSoup, celex_id: str) -> ParsedRegulation:
    """Parse older HTML format with bare <p> tags inside TXT_TE."""
    texte_div = soup.find("div", id="TexteOnly")
    if not texte_div:
        return ParsedRegulation(celex_id=celex_id, title=celex_id, format_type="html_legacy")

    # Get all paragraphs — in old format they're inside TXT_TE
    txt_te = texte_div.find("txt_te")
    container = txt_te if txt_te else texte_div

    paragraphs: list[str] = []
    for p in container.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    # Extract title from first few paragraphs
    doc_title = paragraphs[0] if paragraphs else celex_id

    # Find article boundaries by regex
    article_pattern = re.compile(r"^Article\s+(\d+)$")
    articles: list[Article] = []

    i = 0
    while i < len(paragraphs):
        match = article_pattern.match(paragraphs[i])
        if match:
            art_num = int(match.group(1))

            # Next paragraph is usually the article title/subtitle
            art_title = ""
            body_start = i + 1
            if i + 1 < len(paragraphs):
                next_text = paragraphs[i + 1]
                # If it's short and doesn't start with a number or letter+period,
                # it's likely the subtitle
                if (
                    len(next_text) < 200
                    and not re.match(r"^\d+\.", next_text)
                    and not re.match(r"^Article\s+\d+", next_text)
                    and not next_text.startswith("(")
                ):
                    art_title = next_text
                    body_start = i + 2

            # Collect body until next article or end
            body_parts = []
            j = body_start
            while j < len(paragraphs):
                if article_pattern.match(paragraphs[j]):
                    break
                # Stop at annex boundaries
                if re.match(r"^ANNEX\b", paragraphs[j]):
                    break
                body_parts.append(paragraphs[j])
                j += 1

            article = Article(
                celex_id=celex_id,
                article_number=art_num,
                title=art_title,
                text="\n".join(body_parts),
            )
            articles.append(article)
            i = j
        else:
            i += 1

    return ParsedRegulation(
        celex_id=celex_id,
        title=doc_title,
        articles=articles,
        format_type="html_legacy",
    )


def parse_regulation(html_path: Path | str, celex_id: str) -> ParsedRegulation:
    """Parse a downloaded EUR-Lex HTML file into structured article data.

    Args:
        html_path: Path to the downloaded HTML file.
        celex_id: CELEX number for this regulation.

    Returns:
        ParsedRegulation with extracted articles.
    """
    html_path = Path(html_path)
    content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "lxml")

    fmt = detect_format(soup)

    if fmt == "xhtml":
        return _parse_xhtml(soup, celex_id)
    elif fmt == "xhtml_mid":
        return _parse_xhtml_mid(soup, celex_id)
    else:
        return _parse_html_legacy(soup, celex_id)


def parse_corpus(html_dir: Path | str = "data/raw/html") -> list[ParsedRegulation]:
    """Parse all downloaded HTML files in a directory.

    Returns:
        List of ParsedRegulation objects.
    """
    html_dir = Path(html_dir)
    results = []

    for html_file in sorted(html_dir.glob("*.html")):
        celex_id = html_file.stem
        regulation = parse_regulation(html_file, celex_id)
        results.append(regulation)

    return results
