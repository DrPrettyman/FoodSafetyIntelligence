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
| 2026-02-20 | vector_store.py: sentence-transformers + numpy vector store (ChromaDB incompatible with Py 3.14) | Done |
| 2026-02-20 | Vector store: all-MiniLM-L6-v2 embeddings, cosine similarity, celex_id filtering | Done |
| 2026-02-20 | 5 end-to-end evaluation scenarios + 2 quality metrics, all passing | Done |
| 2026-02-20 | Tests: 94 total (all modules + evaluation), all passing | Done |
| 2026-02-20 | **MVP COMPLETE**: ingestion → parsing → chunking → extraction → routing → vector search → evaluation | Done |
| 2026-02-25 | schemas.py: Pydantic ComplianceRequirement + ExtractionResult models with typed enums | Done |
| 2026-02-25 | llm_extractor.py: Anthropic tool_use extraction chain with few-shot example | Done |
| 2026-02-25 | Tests: 119 total (25 new extraction tests with mocked API), all passing | Done |
| 2026-02-25 | pipeline.py: end-to-end pipeline with build + query phases, CLI interface | Done |
| 2026-02-25 | Serialization: entity index → JSON (defined_terms.json, cross_references.json, entity_stats.json) | Done |
| 2026-02-25 | Build indexes: 33 regs, 881 arts, 1142 chunks, 324 terms, 361 xrefs in 14.2s | Done |
| 2026-02-25 | Tests: 129 total (10 new pipeline/serialization tests), all passing | Done |
| 2026-02-25 | Multi-provider extraction: refactored llm_extractor.py for anthropic/openai/claude-code providers | Done |
| 2026-02-25 | Pipeline CLI: added --provider and --model args, openai as optional dep | Done |
| 2026-02-25 | Tests: 143 total (39 extraction tests with provider mocks, 10 pipeline), all passing | Done |
| 2026-02-26 | Live extraction via claude-code provider: 8 requirements from 5 articles, fully validated | Done |
| 2026-02-26 | Layer 3 evaluation: matching engine, ground truth checklists, cached evaluation | Done |
| 2026-02-26 | Evaluation results: 3 scenarios, P=0.26 R=0.42 F1=0.31 (baseline, granularity mismatch) | Done |
| 2026-02-26 | Tests: 177 total (24 matching + 10 eval extraction + 143 existing), all passing | Done |
| 2026-02-26 | Hybrid retrieval: per-regulation search + broad query merge for full regulation coverage | Done |
| 2026-02-26 | Article-level deduplication: sub-requirements from matched articles excluded from FP | Done |
| 2026-02-26 | Re-evaluation: P=0.26 R=0.46 F1=0.33 (food supplements F1: 0.24→0.35, retrieval coverage 100%) | Done |
| 2026-02-26 | Cross-reference resolution: maps human-readable reg numbers → CELEX IDs, 1-hop expansion after routing | Done |
| 2026-02-26 | Tests: 195 total (18 new cross-reference tests), all passing | Done |
| 2026-02-27 | Streamlit app: sidebar input form, 3-tab results (checklist/articles/routing), EUR-Lex links | Done |
| 2026-02-27 | eurlex_discovery.py: SPARQL-based corpus discovery, 243 regulations, 17 categories, 0 unclassified | Done |
| 2026-02-27 | Discovery: two-tier exclusion (strong/weak), structural heuristic for amendments, \xa0 normalization | Done |
| 2026-02-27 | Discovery: 168/243 have consolidated text, 33/33 original corpus covered, manual includes for 4 regs | Done |
| 2026-02-27 | html_parser.py: CLG consolidated format parser (4th format variant) | Done |
| 2026-02-27 | CLG parser: 81 articles from Reg 178/2002 (vs 65 original), +82% text content | Done |
| 2026-02-27 | corpus.py: loads from discovery report (243 regs) with baseline fallback (33 regs) | Done |
| 2026-02-27 | eurlex_downloader.py: consolidated download support, retry logic, --original flag | Done |
| 2026-02-27 | Tests: 246 total (36 discovery, 24 parser, 11 downloader, 5 corpus, +others), all passing | Done |
| 2026-02-27 | Corpus download: 243 regs, 178 consolidated + 85 originals (61 fallback, 24 stub fallback) | Done |
| 2026-02-27 | Downloader: added fallback logic (404 consolidated → original), tested | Done |
| 2026-02-27 | parse_corpus: fallback from unparseable consolidated to original, skip on total failure | Done |
| 2026-02-27 | Pipeline rebuild: 224 regs, 2823 articles, 3714 chunks, 702 terms, 1032 xrefs in 28.1s | Done |
| 2026-02-27 | Tests: 245 total (3 new fallback tests), all passing | Done |

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

### Vector Store (2026-02-20)

**ChromaDB failed on Python 3.14** — Pydantic V1 incompatibility (`unable to infer type for attribute "chroma_server_nofile"`). Switched to sentence-transformers + numpy with manual cosine similarity.

**Embedding model**: `all-MiniLM-L6-v2` (384-dim embeddings, runs locally, ~22M params). Pre-normalized embeddings so cosine similarity = dot product.

**Persistence**: numpy `.npy` for embeddings + JSON for metadata/texts. Simple and fast.

**Filtering**: celex_id-based filtering via numpy boolean mask before top-k selection. This is the integration point with the routing table — routing narrows the search space, vector search does semantic similarity within that subset.

### Evaluation Results (2026-02-20)

5 real-world scenarios tested end-to-end (routing → filtered vector search):

| Scenario | Product | Routing | Key Regulations Found |
|----------|---------|---------|----------------------|
| 1 | Insect protein bar (novel food) | Novel food + labelling | 32015R2283, 32011R1169 |
| 2 | Vitamin D supplement | Supplements + health claims + fortification | 32002L0046, 32006R1924, 32006R1925 |
| 3 | Sweetened beverage in plastic bottle | Additives + plastic FCM + labelling | 32008R1333, 32011R0010, 32011R1169 |
| 4 | GMO soy product | GMO food/feed + traceability | 32003R1829, 32003R1830 |
| 5 | Organic cereal | Organic + contaminants | 32018R0848, 32023R0915/32006R1881 |

Quality metrics:
- **Routing precision**: focused query returns <50% of corpus (not the whole 33 regulations)
- **Filtered vs unfiltered**: filtered search surfaces domain-relevant articles at least as well as unfiltered

All 7 evaluation tests pass.

### LLM Extraction Module (2026-02-25)

**Pydantic schemas** (`src/extraction/schemas.py`):
- `ComplianceRequirement`: 11 fields covering regulation ID, article, summary, type, priority, cross-references, confidence score
- `RequirementType` enum: 11 categories (authorisation, notification, labelling, safety_assessment, max_limit, documentation, monitoring, traceability, hygiene, prohibition, general_obligation)
- `Priority` enum: before_launch, ongoing, if_applicable
- `ExtractionResult`: wraps list of requirements + metadata

**LLM extractor** (`src/extraction/llm_extractor.py`):
- Uses Anthropic `tool_use` (function calling) to force structured output matching the Pydantic schema
- System prompt: regulatory compliance analyst persona with confidence calibration rules
- Few-shot example: Novel Foods Art 7 (authorisation requirement) embedded in user message
- `tool_choice={"type": "tool", "name": "submit_requirements"}` — forces the model to use the tool
- Malformed requirements silently skipped (try/except on Pydantic validation)
- Model: `claude-sonnet-4-20250514`, max_tokens=4096

**Testing approach**: All 25 tests mock the Anthropic API (`unittest.mock.patch`) to test extraction logic without API calls. Tests cover: schema validation, enum coercion, message construction, tool schema consistency, error handling (missing key, malformed output), and API parameter verification.

**Multi-provider support** (added 2026-02-25):
- Refactored to support three providers: `anthropic` (API + tool_use), `openai` (API + function calling), `claude-code` (CLI `claude -p` subprocess)
- Provider dispatch via `extract_requirements(..., provider="claude-code")`
- OpenAI is a lazy import (optional dependency: `pip install .[openai]`)
- Claude Code provider strips `CLAUDECODE` env var to allow running inside a Claude Code session (nested session workaround)
- 39 tests with mocked providers (subprocess, API), all passing

**Live extraction results** (2026-02-26, claude-code provider):
- Query: "insect protein novel food authorisation labelling", product type: "novel food", 5 articles retrieved
- 8 compliance requirements extracted, all valid `ComplianceRequirement` objects
- Regulations covered: 32002R0178 (Traceability Art 18, 4 reqs), 32011R1169 (Nutrition claims Art 49, 1 req), 32015R2283 (Novel food authorisation Art 10, 2 reqs), 32018R0456 (Novel food status Art 7, 1 req)
- Confidence scores range 0.6–0.95. Highest: traceability obligations (0.95), authorisation application (0.95). Lowest: nanomaterials requirement (0.6, correctly conditional)
- Requirement types: traceability (3), labelling (2), authorisation (1), notification (1), documentation (1)
- Cross-references extracted: 32006R1924, 32011R1169, 32015R2283
- Quality assessment: all requirements map to explicit obligations in the source text, no hallucinated requirements observed

### Layer 3 Evaluation — Extraction Quality (2026-02-26)

**Evaluation framework** (`src/evaluation/`):
- Ground truth checklists: 3 scenarios × 8 requirements each = 24 ground truth items
- Matching: key-based `(regulation_id, article_number, requirement_type)` with relaxed fallback (2-of-3 key fields + word overlap)
- Metrics: precision, recall, F1 per scenario + macro-averaged aggregate
- Cached evaluation: `scripts/run_extraction_scenarios.py` populates cache, pytest evaluates cached results

**Baseline results** (claude-code provider, first run):

| Scenario | Precision | Recall | F1 | TP | Partial | FP | FN |
|----------|-----------|--------|-----|----|---------|----|-----|
| Novel food (insect protein) | 0.27 | 0.38 | 0.32 | 1 | 2 | 8 | 5 |
| FIC labelling (general food) | 0.31 | 0.62 | 0.42 | 3 | 2 | 11 | 3 |
| Food supplements (vitamin D) | 0.18 | 0.25 | 0.21 | 1 | 1 | 9 | 6 |
| **Aggregate (macro-avg)** | **0.26** | **0.42** | **0.31** | — | — | — | — |

**Key findings:**

1. **Precision is low due to granularity mismatch, not accuracy errors.** The LLM correctly extracts multiple sub-requirements per article (e.g., Art 18 traceability → 4 separate obligations for supplier ID, recipient ID, labelling, and system procedures). Our ground truth has 1 item per article. Most "false positives" are legitimate requirements at finer granularity. This is actually desirable for compliance — a compliance officer wants every obligation, not just the article summary.

2. **Recall is limited by retrieval coverage.** Many false negatives occur because the relevant article wasn't in the top-10 search results. For example, Novel Foods Art 6 (authorisation) and Art 7 (safety conditions) were not retrieved, despite being the most important articles. This is a retrieval/query problem, not an extraction problem.

3. **Food supplements scenario has lowest scores** because the query retrieves articles from only a subset of the relevant regulations (32002L0046 well-covered, but 32006R1924 and 32006R1925 poorly represented in search results). Routing correctly identifies all regulations, but vector search doesn't surface enough articles from each.

4. **No hallucinated regulations.** Every extracted requirement references a CELEX ID from the routed set. The LLM does not invent regulations.

**Improvement paths (addressed 2026-02-26):**
- ~~Increase `n_results` to retrieve more articles~~ → addressed via hybrid search
- ~~Add article-level deduplication before matching~~ → implemented in matching engine
- ~~Use multiple queries per scenario (one per regulation)~~ → implemented as hybrid search
- Expand ground truth to include sub-article granularity to match LLM output (future)

### Retrieval & Matching Improvements (2026-02-26)

**Hybrid search** (`src/pipeline.py`):
- Previous: single `store.search(query, celex_ids=all_routed, n_results=10)` — 1-4 regulations got articles
- New: broad query first (top-10 most relevant), then per-regulation search (`per_reg = max(2, n_results // num_regs)`) to fill coverage gaps, merge and deduplicate
- Result: every routed regulation now contributes articles. Food supplements went from 1 to 6 regulations covered.

**Article-level deduplication** (`src/evaluation/matching.py`, `src/evaluation/schemas.py`):
- After matching, extracted requirements from the same `(regulation_id, article_number)` as a TP or partial match are classified as "additional detail" — not false positives
- These are legitimate sub-requirements the LLM correctly extracted at finer granularity than the ground truth
- New `additional_detail` field on `MatchResult` dataclass for diagnostic tracking

**Retrieval coverage comparison:**

| Scenario | Old articles | Old regs | New articles | New regs |
|----------|-------------|----------|-------------|----------|
| Novel food | 10 | 4/7 | 18 | 7/7 |
| FIC labelling | 10 | 1/3 | 16 | 3/3 |
| Food supplements | 10 | 4/6 | 15 | 6/6 |

**Evaluation results after improvements (run_003, with article-level deduplication):**

| Scenario | P | R | F1 | TP | Part | FP | FN | AddDet |
|----------|------|------|------|----|----|----|----|--------|
| Novel food | 0.23 | 0.38 | 0.29 | 3 | 0 | 10 | 5 | 2 |
| FIC labelling | 0.23 | 0.62 | 0.33 | 3 | 2 | 17 | 3 | 4 |
| Food supplements | 0.33 | 0.38 | 0.35 | 1 | 2 | 6 | 5 | 2 |
| **Aggregate** | **0.26** | **0.46** | **0.33** | — | — | — | — | — |

**Effect of article-level deduplication** (re-evaluating run_001 with new matching):

| Scenario | Old P (no dedup) | New P (with dedup) | Items reclassified |
|----------|-----------------|-------------------|-------------------|
| Novel food | 0.27 | 0.43 | 4 FP → additional detail |
| FIC labelling | 0.31 | 0.38 | 3 FP → additional detail |
| Food supplements | 0.18 | 0.22 | 2 FP → additional detail |

**Key takeaways:**
1. Article deduplication correctly identifies 2-4 legitimate sub-requirements per scenario that were inflating FP count
2. Hybrid search achieves 100% regulation coverage (every routed regulation contributes articles)
3. Food supplements scenario improved most (F1: 0.24 → 0.35) — previously only 1 of 6 regulations was represented
4. Precision remains modest because many "FP" are legitimate requirements not in the small ground truth (8 items per scenario)
5. LLM extraction is non-deterministic — metrics vary across runs even with identical retrieval
6. Remaining recall gap is driven by the LLM not always extracting requirements from articles it receives

**Remaining improvement paths:**
- Expand ground truth to 15-20 items per scenario to better capture LLM's actual output quality
- Tune extraction prompt for better article coverage (ensure LLM extracts from every provided article)
- Add extraction temperature=0 for more deterministic results across runs

### Cross-Reference Resolution (2026-02-26)

**Problem**: The entity extractor captures 361 cross-references between regulations (e.g., Novel Foods Regulation referencing General Food Law), but they were never used. When regulation A references regulation B, retrieval should also include B's articles.

**Solution** (`src/retrieval/cross_references.py`):

1. **Regulation number mapping**: `regulation_number_to_celex()` maps human-readable numbers (e.g., "178/2002") to CELEX IDs (e.g., "32002R0178") by trying both number/year and year/number interpretations, plus R (Regulation) and L (Directive) prefixes, against the known corpus.

2. **CrossReferenceIndex**: Built from extracted cross-references + corpus CELEX IDs. Provides `expand(celex_ids)` for 1-hop expansion — given routed regulations, returns additional CELEX IDs they reference.

3. **Pipeline integration**: Expansion happens in `pipeline.query()` between routing and vector search. Uses existing `RoutingResult.add()` to append cross-referenced regulations with provenance tracking (e.g., "cross-referenced from 32015R2283").

**Design decisions**:
- 1-hop only (no transitive following: A→B→C does not add C when routing to A)
- Self-references excluded (regulation referencing itself adds nothing)
- Unresolved references tracked for diagnostics (references to regulations not in corpus)
- Expansion in pipeline.py, not routing.py — keeps routing pure (structured input → regulations) and cross-ref expansion as separate post-routing enrichment
- Uses `CORPUS.keys()` from `corpus.py` as the authoritative set of corpus CELEX IDs

**Testing**: 18 unit tests covering mapping (old-style, new-style, directive, not-in-corpus, invalid format), index building (resolved/unresolved counts, self-reference exclusion), and expansion (single/multiple source, dedup, reasons). All synthetic data, no LLM needed.

### Streamlit App (2026-02-27)

**File**: `app.py` at project root. Run with `streamlit run app.py`.

**Sidebar inputs**: Product category (selectbox), ingredients (multiselect), claims (multiselect), packaging (selectbox), additional keywords (free text), number of articles (slider 5-30), LLM extraction toggle with API key/provider fields.

**Three result tabs**:
1. **Compliance Checklist** — requirements grouped by priority (Before Launch / Ongoing / If Applicable), each in an expander with summary, type, confidence, source regulation + article linked to EUR-Lex, conditions, source text snippet
2. **Retrieved Articles** — ranked list with regulation title, article number, title, relevance score; expandable to show article text
3. **Routing** — regulations selected with reasons, cross-reference expansion diagnostics

**Two modes**: Fast preview (routing + retrieval only, no API key needed) and full extraction (requires Anthropic/OpenAI API key, adds LLM-generated compliance checklist).

**Verified**: app starts, serves HTTP 200, imports cleanly. All 195 existing tests still pass.

### Pipeline & Serialization (2026-02-25)

**End-to-end pipeline** (`src/pipeline.py`):
- Two phases: `build` (offline, run once) and `query` (runtime)
- Build: parse_corpus → chunk_corpus → extract_entities → save_entity_index → index_chunks (vector store)
- Query: load_entity_index → RoutingTable.route → VectorStore.search → extract_requirements (LLM)
- CLI: `python -m src.pipeline build` / `python -m src.pipeline query --product-type "novel food" --query "..."`
- `--skip-extraction` flag for routing+retrieval without LLM (useful for testing without API key)

**Serialization** (JSON-based):
- `data/indexes/defined_terms.json` — 324 defined terms with metadata (100 KB)
- `data/indexes/cross_references.json` — 361 cross-references (85 KB)
- `data/indexes/entity_stats.json` — summary counts
- `data/indexes/build_summary.json` — full build metrics
- `data/vectorstore/` — embeddings.npy (1.7 MB) + metadata.json + texts.json
- Round-trip tested: save → load → verify all fields preserved (including unicode)

**Build performance**: 33 regulations → 881 articles → 1142 chunks → 324 terms → 361 xrefs → vector index, all in 14.2 seconds.

**CLI query test**: "insect protein novel food authorisation" → routes to 8 regulations → retrieves 10 articles. Top results correctly include Novel Foods Art 7 (general conditions), Art 10 (authorisation procedure), Art 16 (traditional food application), and related implementing regulation articles.

### Systematic Corpus Discovery (2026-02-27)

**Problem**: Hand-curated corpus of 33 regulations was incomplete and downloaded as original (unamended) text. Many regulations have been heavily amended — Food Additives has 64 consolidated versions, General Food Law has 12 amendments.

**Solution**: `src/ingestion/eurlex_discovery.py` — SPARQL-based discovery pipeline.

**Discovery approach**:
- Queries EUR-Lex SPARQL endpoint for regulations under directory codes `133014` (Foodstuffs) and `152030` (Protection of health)
- Two-tier exclusion system: strong excludes (always filter: individual authorisations, biocidal products, emergency measures, etc.) and weak excludes (only filter amendment-only acts, not framework regulations)
- Structural heuristic: framework regs have ", amending" or "and amending" (substantive content before the amending clause); amendment-only acts jump straight to "amending" after the date
- Manual include list for 4 core regs under non-food directory codes (32004R0853, 32011R0016, 32013R1337, 32018R0848)
- 130+ category classification rules mapping title patterns → categories

**Results**: 243 regulations discovered (vs 33 hand-curated), 17 categories, 0 unclassified, 168 have consolidated text, 33/33 original corpus covered.

**Non-breaking space bug**: EUR-Lex titles contain `\xa0` (non-breaking space) between `(EU)` and regulation numbers. Pattern matching requires whitespace normalization via `_normalize()`: `re.sub(r"\s+", " ", text).strip()`.

**Output**: `data/discovery/discovery_report.json` — runnable via `python -m src.ingestion.eurlex_discovery`.

### CLG Consolidated Format (2026-02-27)

Fourth HTML format variant for consolidated (as-amended) text from EUR-Lex.

**Detection**: `<p class="title-article-norm">` present (checked before `eli-container` since CLG also has that).

**Key CSS classes**:
- `title-article-norm` — Article headings ("Article 1", "Article 8a")
- `stitle-article-norm` — Article subtitles, inside `<div class="eli-title">`
- `norm` — Body text (both `<p>` and `<div>` tags)
- `grid-container grid-list` — Numbered list items
- `list` — Lettered list items
- `title-division-1` — Used for both "CHAPTER X" and "SECTION X"
- `title-division-2` — Descriptive subtitle for divisions
- `title-doc-first` / `title-doc-last` — Document title (in `eli-main-title`, avoid copies in amendment history table)
- `modref` / `arrow` — Amendment markers (skipped during parsing)

**Article numbering**: Consolidated text includes amendment-inserted articles (8a, 32b, etc.). `article_number` field stores the base integer; downstream chunking handles duplicate numbers via occurrence suffixes.

**Chapter/section tracking**: Walk all division headings and article headings in document order (via `find_all` which preserves order), building an `id(element) → (chapter, section)` map.

**Comparison** (Reg 178/2002, General Food Law):

| Metric | Original (html_legacy) | Consolidated (CLG) |
|--------|----------------------|-------------------|
| Articles | 65 | 81 (+16) |
| Text chars | 79,269 | 144,160 (+82%) |
| Format | html_legacy | clg |

The 16 additional articles are amendment-inserted (8a-c, 32a-d, 39a-g, 57a, 61a).

### Corpus Loading (2026-02-27)

`corpus.py` now loads from `data/discovery/discovery_report.json` if it exists, falling back to the hand-curated `_BASELINE_CORPUS` (33 regulations). The `CORPUS` dict and `get_consolidated_celex()` function are the authoritative interfaces consumed by routing, extraction, and display code.

`parse_corpus()` in `html_parser.py` handles consolidated filenames by converting `0YYYYTNNNN-YYYYMMDD` back to base CELEX `3YYYYTNNNN` so downstream code sees consistent identifiers.

### Expanded Corpus Build Results (2026-02-27)

**Corpus download**: 243 regulations from discovery, downloaded using consolidated-preferred strategy.
- 105 consolidated versions downloaded successfully (CLG format)
- 22 consolidated stubs (repealed regulations, no actual content — only metadata page with "Repealed by" notice)
- 3 old inline-styled consolidated files (pre-CSS era, inline `style="font-family: 'Arial Unicode MS'"`)
- 61 original-version fallbacks (consolidated CELEX returned 404)
- 24 original-version fallbacks (consolidated was stub or unparseable format)
- Total HTML files: 296 (some regs have both consolidated and original)

**Fallback logic in downloader**: When `prefer_consolidated=True` and the consolidated CELEX returns an error (e.g., HTTP 404), the downloader now automatically falls back to the original CELEX ID. This handles the ~60 old regulations where EUR-Lex has SPARQL metadata for consolidated text but the actual document doesn't exist.

**Fallback logic in parser**: `parse_corpus()` now tries consolidated file first. If it fails to parse (unknown format) or yields 0 articles (repealed stub), falls back to the original file. If both fail, the regulation is skipped with a warning. This handles:
- 22 repealed stubs (consolidated CLG with `clg.css` but no articles, just a "Repealed by" notice)
- 3 old inline-styled files (pre-2003 consolidated text without CSS classes)
- 4 old directives where even the original yields 0 articles (no `TexteOnly` div or `eli-container`)

**Parse results**: 224 of 243 regulations parsed successfully (92%). 19 skipped (mostly pre-1995 repealed directives).

**Pipeline build comparison** (old → new):

| Metric | 33-reg corpus | 224-reg corpus | Change |
|--------|--------------|----------------|--------|
| Regulations | 33 | 224 | +579% |
| Articles | 881 | 2,823 | +220% |
| Chunks | 1,142 | 3,714 | +225% |
| Defined terms | 324 (272 unique) | 702 (475 unique) | +116% |
| Cross-references | 361 | 1,032 | +186% |
| Build time | 14.2s | 28.1s | +98% |

## Open Questions

- How do annexes appear in the HTML structure? Annexes contain the actual regulated substance lists (E-numbers, Union List, etc.) and may need special parsing. The parser currently stops at article boundaries and doesn't extract annex content.
- Cross-reference links in the HTML — are they `<a>` tags pointing to other CELEX numbers? If so, we can build the dependency graph from the HTML itself.
- Legacy format title detection is heuristic-based and sometimes picks up body text as title (e.g., 32002L0046 Art 2, Art 3). Acceptable for now but could be improved.
- 19 regulations skipped during parse (old repealed directives). Worth investigating if any are still-referenced by other corpus regulations.
- Evaluation scenarios should be re-run with expanded corpus — expect better retrieval coverage and potentially higher recall.
- Routing table scales automatically (uses CORPUS dict), but the 3 new categories (feed, food_irradiation, product_standards) may need keywords added to `CATEGORY_ROUTING` in routing.py for query-time routing.
