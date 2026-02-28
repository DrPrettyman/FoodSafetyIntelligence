"""
Parse EUR-Lex HTML/XHTML into structured article data.

Handles four format variants:
- CLG consolidated (post-2004): CSS classes .title-article-norm, .norm, .eli-container
- Newer XHTML (post-~2013): CSS classes .oj-ti-art, .oj-sti-art, .eli-container
- Mid-era XHTML (~2004-2012): same classes without "oj-" prefix (.ti-art, .sti-art)
- Older HTML (pre-~2004): bare <p> tags inside <div id="TexteOnly"> / <TXT_TE>

Output: list of Article dicts, each with celex_id, article_number, title, text,
chapter, section.
"""

import logging
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

logger = logging.getLogger(__name__)

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
    format_type: str = ""  # "clg", "xhtml", "xhtml_mid", or "html_legacy"


def detect_format(soup: BeautifulSoup) -> str:
    """Detect whether this is CLG consolidated, newer XHTML, mid-era XHTML, or older HTML."""
    # CLG consolidated uses title-article-norm within eli-container
    if soup.find(class_="title-article-norm"):
        return "clg"
    if soup.find(class_="eli-container"):
        return "xhtml"
    if soup.find(class_="ti-art"):
        return "xhtml_mid"
    if soup.find("div", id="TexteOnly"):
        return "html_legacy"
    raise ValueError("Unknown EUR-Lex HTML format: no eli-container, ti-art, or TexteOnly div found")


def _parse_clg(soup: BeautifulSoup, celex_id: str) -> ParsedRegulation:
    """Parse CLG consolidated format.

    Structure: eli-container > eli-subdivision (chapter) > div > eli-subdivision (article).
    Each article eli-subdivision contains:
      - <p class="title-article-norm"> — "Article N" or "Article Na" (amendment inserts)
      - <div class="eli-title"> wrapping <p class="stitle-article-norm"> — subtitle
      - <p|div class="norm"> — body paragraphs
      - <div class="grid-container grid-list"> — numbered list items
      - <p class="list"> — lettered list items
    Chapter/section context from title-division-1/title-division-2 paragraphs.
    Division-1 may be "CHAPTER X" or "SECTION X"; division-2 is descriptive subtitle.
    """
    # Extract document title from eli-main-title (avoid amendment history table)
    title_parts = []
    main_title_div = soup.find("div", class_="eli-main-title")
    if main_title_div:
        for p in main_title_div.find_all("p", class_="title-doc-first"):
            text = p.get_text(strip=True)
            if text and not text.startswith("of "):
                title_parts.append(text)
        for p in main_title_div.find_all("p", class_="title-doc-last"):
            text = p.get_text(strip=True)
            if text:
                title_parts.append(text)
    doc_title = " — ".join(title_parts[:2]) if title_parts else celex_id

    # Map each article subdivision to its chapter/section context.
    # Walk all title-division-1 and title-article-norm elements in document order
    # to build context. BeautifulSoup's find_all preserves document order.
    landmark_classes = {"title-division-1", "title-division-2", "title-article-norm"}
    landmarks = soup.find_all(
        lambda tag: isinstance(tag, Tag)
        and bool(set(tag.get("class", [])) & landmark_classes)
    )

    current_chapter = ""
    current_section = ""
    art_context: dict[int, tuple[str, str]] = {}  # id(element) → (chapter, section)

    for el in landmarks:
        el_classes = set(el.get("class", []))
        if "title-division-1" in el_classes:
            d1_text = el.get_text(strip=True)
            # Find paired div-2 (next sibling)
            d2 = el.find_next_sibling("p", class_="title-division-2")
            d2_text = d2.get_text(strip=True) if d2 else ""
            label = f"{d1_text} — {d2_text}" if d2_text else d1_text
            if d1_text.startswith("CHAPTER"):
                current_chapter = label
                current_section = ""
            else:
                current_section = label
        elif "title-article-norm" in el_classes:
            art_context[id(el)] = (current_chapter, current_section)

    articles: list[Article] = []

    for subdivision in soup.find_all("div", class_="eli-subdivision"):
        art_heading = subdivision.find("p", class_="title-article-norm", recursive=False)
        if not art_heading:
            continue

        heading_text = art_heading.get_text(strip=True)
        # Match "Article 8", "Article 8a", "Article 32b" etc.
        art_match = re.match(r"Article\s+(\d+[a-z]*)", heading_text, re.IGNORECASE)
        if not art_match:
            continue

        art_id = art_match.group(1)  # e.g. "8", "8a", "32b"
        art_num = int(re.match(r"\d+", art_id).group())

        # Article subtitle from eli-title > stitle-article-norm
        art_title = ""
        eli_title = subdivision.find("div", class_="eli-title", recursive=False)
        if eli_title:
            stitle = eli_title.find("p", class_="stitle-article-norm")
            if stitle:
                art_title = stitle.get_text(strip=True)

        chapter, section = art_context.get(id(art_heading), ("", ""))

        # Collect body text from norm, list, and grid-list elements
        body_parts = []
        skip_classes = {"title-article-norm", "stitle-article-norm", "eli-title",
                        "modref", "arrow", "footnote", "title-fam-member-star"}

        for child in subdivision.descendants:
            if not isinstance(child, Tag):
                continue
            child_classes = set(child.get("class", []))
            if child_classes & skip_classes:
                continue
            if "norm" in child_classes or "list" in child_classes:
                # Only collect text from leaf norm/list elements (avoid double-counting
                # when a div.norm contains nested elements)
                if not child.find(class_="norm"):
                    text = child.get_text(strip=True)
                    if text:
                        body_parts.append(text)
            elif "grid-container" in child_classes:
                text = child.get_text(strip=True)
                if text:
                    body_parts.append(text)

        article = Article(
            celex_id=celex_id,
            article_number=art_num,
            title=art_title,
            text="\n".join(body_parts),
            chapter=chapter,
            section=section,
        )
        articles.append(article)

    return ParsedRegulation(
        celex_id=celex_id,
        title=doc_title,
        articles=articles,
        format_type="clg",
    )


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

    if fmt == "clg":
        return _parse_clg(soup, celex_id)
    elif fmt == "xhtml":
        return _parse_xhtml(soup, celex_id)
    elif fmt == "xhtml_mid":
        return _parse_xhtml_mid(soup, celex_id)
    else:
        return _parse_html_legacy(soup, celex_id)


def _consolidated_to_base_celex(filename_stem: str) -> str:
    """Convert a consolidated CELEX (e.g. 02002R0178-20260101) to base CELEX (32002R0178).

    Consolidated CELEX IDs start with '0' and have a date suffix.
    Base CELEX IDs start with '3' (sector 3 = legislation).
    If the filename is already a base CELEX, return it unchanged.
    """
    if re.match(r"^0\d{4}[RL]\d{4}-\d{8}$", filename_stem):
        return "3" + filename_stem[1:10]
    return filename_stem


def parse_corpus(html_dir: Path | str = "data/raw/html") -> list[ParsedRegulation]:
    """Parse all downloaded HTML files in a directory.

    Handles both original (3YYYYTNNNN) and consolidated (0YYYYTNNNN-YYYYMMDD)
    filenames. Consolidated files are mapped to their base CELEX ID so the
    rest of the pipeline sees consistent identifiers.

    When both original and consolidated files exist for the same base CELEX ID,
    the consolidated version is tried first (more complete, includes amendments).
    Falls back to original if consolidated fails to parse or yields 0 articles
    (e.g. repealed regulation stubs).

    Returns:
        List of ParsedRegulation objects.
    """
    html_dir = Path(html_dir)

    # Collect all files per base CELEX, tracking consolidated vs original
    celex_files: dict[str, dict[str, Path]] = {}  # {base_celex: {"consolidated": path, "original": path}}
    for html_file in sorted(html_dir.glob("*.html")):
        base_celex = _consolidated_to_base_celex(html_file.stem)
        is_consolidated = html_file.stem != base_celex
        if base_celex not in celex_files:
            celex_files[base_celex] = {}
        key = "consolidated" if is_consolidated else "original"
        celex_files[base_celex][key] = html_file

    results = []
    for celex_id, files in sorted(celex_files.items()):
        # Try consolidated first, then original
        candidates = []
        if "consolidated" in files:
            candidates.append(("consolidated", files["consolidated"]))
        if "original" in files:
            candidates.append(("original", files["original"]))

        parsed = None
        for variant, html_file in candidates:
            try:
                regulation = parse_regulation(html_file, celex_id)
                if regulation.articles:
                    parsed = regulation
                    break
                else:
                    logger.warning(
                        f"No articles extracted from {variant} {html_file.name} "
                        f"for {celex_id}, trying next variant"
                    )
            except (ValueError, Exception) as e:
                logger.warning(
                    f"Failed to parse {variant} {html_file.name} "
                    f"for {celex_id}: {e}, trying next variant"
                )

        if parsed:
            results.append(parsed)
        else:
            logger.warning(f"Skipping {celex_id}: no parseable file found")

    return results
