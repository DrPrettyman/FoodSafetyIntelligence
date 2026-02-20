# Project Notes — EU Food Safety Regulatory Intelligence Engine

## Progress Log

| Date | What was done | Status |
|------|---------------|--------|
| 2026-02-20 | Project scaffolding: created CLAUDE.md, notes.md | Done |
| 2026-02-20 | EUR-Lex data access research: tested Cellar REST API, SPARQL, website, Python packages | Done |
| 2026-02-20 | Project structure: pyproject.toml, directories, __init__.py files, .env.example | Done |
| 2026-02-20 | corpus.py: 30 CELEX numbers across 15 regulatory categories | Done |
| 2026-02-20 | eurlex_downloader.py: tested on 3 docs, all downloaded OK | Done |
| 2026-02-20 | Tests: 12 tests for corpus + downloader, all passing | Done |
| 2026-02-20 | HTML structure analysis: examined both XHTML and old HTML formats | Done |
| 2026-02-20 | html_parser.py: parses both formats, extracts articles with metadata | Done |
| 2026-02-20 | Parser test results: 32015R2283→36 arts, 32002R0178→65 arts, 32008R1333→35 arts | Done |
| 2026-02-20 | Tests: 21 total (5 corpus, 7 downloader, 9 parser), all passing | Done |
| 2026-02-20 | Full corpus: downloaded 33 docs (16 MB), 0 errors | Done |
| 2026-02-20 | Parser: discovered 3rd format variant (xhtml_mid, ~2004 era), added handler | Done |
| 2026-02-20 | Full corpus parse: 33 regulations, 881 articles, all parse OK | Done |
| 2026-02-20 | Tests: 25 total, all passing (including full corpus parse test) | Done |
| 2026-02-20 | chunking.py: article-aware chunking with sub-chunking at paragraph boundaries | Done |
| 2026-02-20 | Chunking results: 1142 chunks, 1.2M chars, avg 1084 chars/chunk | Done |
| 2026-02-20 | Fixed duplicate chunk IDs: amending regulation 32019R1381 has repeated article numbers | Done |
| 2026-02-20 | Tests: 42 total (5 corpus, 7 downloader, 13 parser, 17 chunking), all passing | Done |
| 2026-02-20 | entity_extractor.py: regex-based extraction of defined terms + cross-references | Done |
| 2026-02-20 | Extraction results: 324 defined terms (272 unique), 361 cross-references | Done |
| 2026-02-20 | Tests: 58 total (all modules), all passing | Done |
| 2026-02-20 | routing.py: deterministic routing table from structured parameters to regulations | Done |
| 2026-02-20 | Routing: category mapping + entity matching, always includes General Food Law + FIC | Done |
| 2026-02-20 | Tests: 77 total (5 corpus, 7 downloader, 13 parser, 17 chunking, 16 entity, 19 routing), all passing | Done |

## Data Notes

### EUR-Lex Access Methods Tested (2026-02-20)

**1. Cellar REST API — WORKS, recommended approach**
- Endpoint: `http://publications.europa.eu/resource/celex/{CELEX_ID}`
- No authentication required. No API key, no registration.
- Uses HTTP content negotiation. Must set headers:
  - `Accept: text/html, application/xhtml+xml;q=0.9`
  - `Accept-Language: eng`
- CRITICAL: Must accept BOTH `text/html` and `application/xhtml+xml`. Older documents (pre-~2010) are `text/html` only. Requesting only `application/xhtml+xml` returns 404 for those.
- Server returns a 303 redirect to the actual Cellar manifestation URL, e.g.:
  `http://publications.europa.eu/resource/cellar/d2e5f917-9fd7-11e5-8781-01aa75ed71a1.0006.03/DOC_1`
- No rate limit headers observed. Added 1s delay between requests to be polite.

Test results:

| CELEX | Document | Size | Content-Type |
|-------|----------|------|-------------|
| 32015R2283 | Novel Foods Regulation | 200,184 bytes | application/xhtml+xml |
| 32002R0178 | General Food Law | 114,573 bytes | text/html |
| 32004R0852 | Food Hygiene | 182,141 bytes | application/xhtml+xml |
| 32004R0853 | Hygiene of foodstuffs of animal origin | 671,259 bytes | application/xhtml+xml |
| 32017R0625 | Official Controls | 1,687,294 bytes | application/xhtml+xml |

Estimated total corpus size for ~120 docs: 30-60 MB. Download time ~2-3 min with delays.

**2. EUR-Lex website URLs — DO NOT WORK for programmatic access**
- URL pattern: `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32015R2283`
- Returns HTTP 202 with an AWS WAF JavaScript challenge page. The response contains:
  `<script src="https://3e3378af7cd0.a62927d9.eu-west-1.token.awswaf.com/.../challenge.js">`
- Would require a headless browser (Selenium/Playwright) to bypass — unnecessary when Cellar works.

**3. SPARQL Endpoint (Cellar) — WORKS for metadata/discovery**
- Endpoint: `https://publications.europa.eu/webapi/rdf/sparql`
- No authentication required.
- Request: GET with `query` param, `Accept: application/sparql-results+json`
- Useful for discovering documents by topic, but not needed for download if we already have CELEX numbers.
- Key EuroVoc URIs for food safety:
  - `http://eurovoc.europa.eu/6569` — "food safety"
  - `http://eurovoc.europa.eu/1590` — "foodstuffs legislation"
  - `http://eurovoc.europa.eu/2735` — "foodstuff"
  - `http://eurovoc.europa.eu/1284` — "human nutrition"
  - `http://eurovoc.europa.eu/7126` — "European Food Safety Authority"
- Resource type URIs: `REG` for regulations, `DIR` for directives.
- Simple queries with specific URIs return fast. Regex-based or `GROUP BY` queries on large result sets can time out.
- From Jan 2026: results limited to 10,000 per query (irrelevant for our ~120 doc use case).

Working SPARQL query for food safety regulations:
```sparql
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?celex ?title
WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_has_resource-type <http://publications.europa.eu/resource/authority/resource-type/REG> .
  ?work cdm:work_is_about_concept_eurovoc <http://eurovoc.europa.eu/6569> .
  ?expression cdm:expression_belongs_to_work ?work .
  ?expression cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  ?expression cdm:expression_title ?title .
}
ORDER BY DESC(?celex)
LIMIT 30
```

### HTML Format Differences

Two distinct formats encountered:

**Newer format (post-~2013, XHTML):**
- Content-Type: `application/xhtml+xml;charset=UTF-8`
- Generated by CONVEX converter
- Has ELI (European Legislation Identifier) semantic markup
- Key CSS classes for parsing:
  - `.eli-container` — root container
  - `.eli-main-title` — regulation title
  - `.eli-subdivision` — structural divisions
  - `.oj-ti-section-1` — Chapter headings
  - `.oj-ti-section-2` — Section headings
  - `.oj-ti-art` — Article headings (e.g., "Article 1")
  - `.oj-sti-art` — Article subtitles (e.g., "Subject matter and purpose")
  - `.oj-normal` — Normal paragraph text
  - `.oj-doc-ti` — Document title text
  - `.oj-note` — Footnotes
- Structural IDs: `tit_1`, `pbl_1` (preamble), `art_N` (articles), `enc_1` (enacting terms)

**Mid-era format (~2004-2012, XHTML without ELI):**
- Same CSS class patterns as newer XHTML but WITHOUT the `oj-` prefix
- Uses: `.ti-art`, `.sti-art`, `.normal`, `.ti-section-1`, `.doc-ti`
- Articles are direct children of `<body>`, not nested in `eli-subdivision` divs
- Parser walks next siblings from each `ti-art` heading
- Only 2 docs in our corpus use this format: 32004R0852, 32004R0853
- Detected by presence of `.ti-art` class when no `.eli-container` exists

**Older format (pre-~2004, HTML 4.01):**
- Content-Type: `text/html;charset=UTF-8`
- Dublin Core metadata in `<meta>` tags
- Main content in `<div id="TexteOnly">` → `<TXT_TE>` tag
- All content is bare `<p>` tags with NO CSS classes
- Articles identifiable only by text pattern: `<p>Article N</p>` followed by subtitle paragraph
- 32002R0178 (General Food Law) has 65 articles in this format
- Parsing requires regex-based article boundary detection, not CSS class matching

**Formex 4 XML (`fmx4`):** The `fmx4` format available from Cellar is NOT the full text — it's a metadata wrapper/TOC. Not useful for our purposes. XHTML/HTML is the way to go.

### Python Packages Evaluated

| Package | Version | Last Updated | Status |
|---------|---------|-------------|--------|
| `eurlex` | 0.1.4 | Jun 2023 | Uses EUR-Lex website URLs — likely broken due to WAF |
| `eurlex-toolbox` | N/A | May 2024 (GitHub only) | Not on PyPI. Pre-built corpus (2009-2019). Not useful for targeted downloads. |
| `pyeurlex` | 0.2.9 | Sep 2022 | SPARQL-based. Stale. |
| `eurlex-parser` | 0.0.13 | Aug 2024 | Has `get_articles_by_celex_id()`. Most recent. Worth investigating for parsing, not download. |

**Decision: Write our own downloader.** The Cellar REST API is simple enough that a custom function is better than depending on stale third-party packages. Download is ~15 lines of code.

## What Worked

- **Cellar REST API** is the clear winner for document download. Simple, fast, no auth, no rate limits observed.
- **SPARQL endpoint** is useful for corpus discovery (finding CELEX numbers by EuroVoc topic).
- **Content negotiation** with both `text/html` and `application/xhtml+xml` in the Accept header handles both old and new documents.
- **pyproject.toml**: build-backend must be `setuptools.build_meta`, NOT `setuptools.backends._legacy:_Backend` (the latter doesn't exist and breaks `pip install -e`).
- **Python 3.14** is what's installed (`/opt/homebrew/bin/python3`). Use `python3` not `python`. Venv at `.venv/`.

## What Didn't Work

- **EUR-Lex website URLs** are now behind AWS WAF bot protection (as of testing date). Returns a JS challenge page, not document content. Do not use for programmatic access.
- **Existing Python packages** are all stale (oldest: 2022, newest: Aug 2024). None recommended for production use.
- **Formex 4 XML** format from Cellar is just a metadata wrapper, not the full document text. XHTML is the correct format.
- **Requesting only `application/xhtml+xml`** in the Accept header fails for older documents (returns 404). Must include `text/html` as well.
- **pyproject.toml build-backend** — `setuptools.backends._legacy:_Backend` does NOT exist. Must use `setuptools.build_meta`.

### Parser Results (2026-02-20)

Parser tested on 3 downloaded regulations:

| CELEX | Format | Articles Found | Art 1 Title | Definitions Art |
|-------|--------|---------------|-------------|-----------------|
| 32015R2283 | xhtml | 36 | Subject matter and purpose | Art 3, 4817 chars |
| 32002R0178 | html_legacy | 65 | Aim and scope | Art 3, 4281 chars |
| 32008R1333 | xhtml | 35 | Subject matter | Art 3, 4004 chars |

Both format parsers extract correct article counts, titles, and body text. Definitions articles all have substantial content (>4000 chars), suitable for entity extraction.

### Full Corpus Parse Results (2026-02-20)

33 regulations downloaded (16 MB total), all parse successfully. 881 articles total.

Format breakdown: 27 xhtml (ELI), 2 xhtml_mid, 4 html_legacy.

Largest docs by article count: 32017R0625 (Official Controls, 167 arts), 32002R0178 (General Food Law, 65 arts), 32018R0848 (Organic, 61 arts).

Smallest: 32012R0432 (Health claims list, 2 arts), 32017R2470 (Novel food Union List, 2 arts) — these are mostly annex-based docs where the articles just say "see annex."

### Chunking Results (2026-02-20)

1142 total chunks from 881 articles across 33 regulations. 1.2M characters total.

| Metric | Value |
|--------|-------|
| Total chunks | 1142 |
| Total characters | 1,239,023 |
| Avg chars/chunk | 1084 |
| Single-chunk articles | 704 |
| Sub-chunked article parts | 438 |
| Chunks over 2000 chars | 35 |

The 35 oversized chunks are articles where a single paragraph exceeds the max limit — the chunker can't split within a paragraph. Largest is 2212 chars (32018R0848 Art 39), only ~10% over the 2000 limit. Acceptable.

**Duplicate article numbers**: Regulation 32019R1381 (Transparency Regulation) is an amending regulation that inserts articles into other regulations. Its HTML contains multiple "Article 8", "Article 32", "Article 39" headings (referring to articles being inserted into target regulations). Fixed by adding `_occ{N}` suffix to chunk IDs for duplicates.

### Entity Extraction Results (2026-02-20)

324 defined terms extracted (272 unique) from 24 of 33 regulations. 361 cross-references to other regulations.

The 9 regulations with no extracted terms are: annex-based docs (32012R0231, 32012R0432, 32017R2470, 32016R0127), regulations that reference definitions from other regs without defining their own (32004R0853, 32006R1881, 32008R1331, 32002L0046), and the amending regulation 32019R1381.

Key terms found across multiple regulations: "food" (5 regs), "feed" (3 regs), "food additive" (2 regs), "novel food", "traceability", "hazard", "risk", etc.

Cross-reference network: Regulation (EC) No 178/2002 (General Food Law) is the most referenced regulation — foundational definitions that most other food safety regulations point to.

**Regex patterns used:**
- Single quotes: `'term' means ...` / `'term' shall mean ...`
- Double quotes (including smart quotes): `"term" means ...`
- Parenthetical aliases: `"food" (or "foodstuff") means ...`
- Hereinafter clause: `"food hygiene", hereinafter called "hygiene", means ...`

## Open Questions

- How do annexes appear in the HTML structure? Annexes contain the actual regulated substance lists (E-numbers, Union List, etc.) and may need special parsing. The parser currently stops at article boundaries and doesn't extract annex content.
- Cross-reference links in the HTML — are they `<a>` tags pointing to other CELEX numbers? If so, we can build the dependency graph from the HTML itself.
- Legacy format title detection is heuristic-based and sometimes picks up body text as title (e.g., 32002L0046 Art 2, Art 3). Acceptable for now but could be improved.
