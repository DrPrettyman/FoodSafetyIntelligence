# L1: EU Food Safety Regulatory Intelligence Engine

## Full Project Plan

---

## 1. The Business Problem

A food company wants to launch a new product — say a protein bar with novel ingredients, or a traditional food from a third country — into the EU market. Before it can sell a single unit, it must answer questions like:

- Is this ingredient classified as a "novel food" under Regulation (EU) 2015/2283?
- Does the product need EFSA safety assessment before authorisation?
- What labelling requirements apply under the Food Information to Consumers Regulation (EU) 1169/2011?
- Are there maximum permitted levels for any additive or contaminant in this product category?
- What are the applicable food contact material regulations if the packaging is plastic?
- Which harmonised standards apply, and are there pending amendments?

Today, answering these questions requires either:

- **Regulatory consulting firms** billing €300–500/hour to manually cross-reference EUR-Lex documents, EFSA guidance, and national transposition measures
- **Compliance SaaS platforms** (SGS Digicomply, FoodChain ID, Registrar Corp) charging €10K–50K/year for access to curated regulatory databases
- **In-house compliance teams** spending days per product launch navigating dense legal text

The cost is real. The EU food safety regulatory framework alone spans hundreds of regulations, directives, and implementing acts. Cross-referencing them — "Regulation X says this, but Directive Y amends Article 3 of Regulation Z" — is exactly the kind of structured reasoning task where RAG + LLM can demonstrably add value.

**Resume line (draft):** "Built a regulatory intelligence system over 120 EU food safety laws: extracted every regulated entity to build structured input options and deterministic routing, then used LLM extraction to generate compliance checklists with 82% precision against expert-validated ground truth. Deployed as a Streamlit app."

---

## 2. Why This Problem, For This Portfolio

This project is selected for specific strategic reasons:

**Domain alignment with target roles.** Revolut, Clarity AI, and similar fintech/ESG companies operate under heavy EU regulation. Demonstrating that you can build intelligence systems over EU regulatory text — regardless of the specific domain — signals directly relevant capability. The domain (food safety) is chosen because it connects to the Private Label project, but the underlying skills (legal RAG, structured extraction, cross-reference resolution) transfer to any regulatory domain.

**Ties to the Private Label project.** The Private Label project analyses food product data from Open Food Facts and European retailer catalogues. L1 answers the natural follow-up: "OK, we've identified a market gap for product category X — now what regulations does a company need to comply with to actually launch it?" This connection between projects shows portfolio coherence and systems thinking.

**Genuine LLM differentiation.** A simple keyword search over EUR-Lex already exists (EUR-Lex has its own search). The value of an LLM-based system is in two specific capabilities: structured extraction (turning dense legal prose into typed compliance checklists) and cross-reference resolution (following "as amended by" chains across documents). These are the tasks where LLMs genuinely add value. Notably, the *input* side does not need an LLM — product parameters can be collected via structured forms and routed deterministically to the relevant regulatory domains. This keeps the LLM focused on what it's actually good at.

**Verifiable outputs.** Unlike a chatbot where quality is subjective, regulatory compliance requirements are factual. Either the system correctly identifies that a product needs EFSA novel food assessment, or it doesn't. This makes evaluation concrete and measurable.

---

## 3. Novelty Assessment

### What already exists

| Project | What it does | How we differ |
|---|---|---|
| **Chat-EUR-Lex** (Aptus-AI, 2023-24) | Basic RAG chatbot over EUR-Lex. Open-ended Q&A. No structured output, no evaluation framework, no domain focus. 6 GitHub stars. | We do **structured extraction** (not chat), **domain-focused** (food safety, not all EU law), and include **rigorous evaluation** against ground truth checklists. |
| **Energy-Law Query-Master** | RAG Q&A over EUR-Lex energy legislation. Uses Ollama + LangChain + Gradio. | Similar architecture but different domain. No structured output extraction, no evaluation metrics reported. |
| **LexDrafter** | RAG for drafting *definitions* in new legislative documents. Academic project. | Completely different task (drafting vs. querying). |
| **EUR-Lex multi-label classification** (multiple) | Classify documents by EUROVOC labels. Classic NLP task, no RAG. | Different task entirely. We retrieve and extract, not classify. |
| **GraphCompliance** (arXiv, Oct 2025) | Knowledge-graph + RAG for GDPR compliance checking. Research paper. | Academic research, not a portfolio project. Different domain (GDPR compliance of software, not food safety). But the paper is worth citing — it validates that regulatory compliance is an active research area. |
| **Generic regulatory RAG blogs** (Medium, various) | Tutorials showing "how to build a RAG over legal documents." Typically use a single regulation (GDPR), no evaluation. | We use a **multi-regulation corpus** with cross-references, **structured output**, and **quantified evaluation**. |

### Our differentiation (4 layers)

1. **Corpus entity extraction:** We don't just index the documents — we extract every regulated entity and build a structured domain model. This becomes both the UI and the routing logic.
2. **Structured input + deterministic routing:** No free-text query parsing. User selects from corpus-derived options. Routing is a lookup, not a prediction. Independently testable.
3. **Domain focus:** EU food safety regulation specifically — not "all EU law" (too broad) or "GDPR" (overdone)
4. **Rigorous evaluation:** Five layers of evaluation including entity coverage, routing accuracy, retrieval quality, extraction precision/recall, and failure mode analysis. Measured against expert-validated compliance checklists.

---

## 4. Data Sources

### Primary: EUR-Lex Food Safety Corpus

**Access method:** EUR-Lex provides multiple machine-readable access options:
- **Data Dump:** Bulk download of all legal acts in force (requires EU Login account, free). Available as structured XML (Formex format).
- **SPARQL endpoint (Cellar):** Query metadata, relationships, and document identifiers programmatically. Well-documented CDM (Common Data Model).
- **REST API:** Retrieve specific documents by CELEX identifier in HTML, XML, PDF, or RDF.
- **Python tooling:** The `eurlex-toolbox` package handles XML-Formex download and parsing. The R `eurlex` package (Ovádek, 2021) provides SPARQL query builders — logic can be adapted to Python.

**Scope for this project:** We do NOT index all of EUR-Lex (that would be 100K+ documents and would dilute retrieval quality). Instead, we curate a focused corpus:

| Category | Key regulations | Approx. documents |
|---|---|---|
| General food law | Reg. 178/2002, Reg. 2019/1381 | ~10 |
| Novel foods | Reg. 2015/2283, Impl. Regs. 2017/2468, 2017/2469 | ~15 |
| Food additives | Reg. 1333/2008 + amendments | ~20 |
| Food contact materials | Reg. 1935/2004, Reg. 10/2011, Reg. 2022/1616 | ~15 |
| Labelling (FIC) | Reg. 1169/2011 + amendments | ~10 |
| Nutrition & health claims | Reg. 1924/2006 + amendments | ~10 |
| Contaminants | Reg. 2023/915 (max levels), Reg. 2017/625 (controls) | ~15 |
| Organic production | Reg. 2018/848 | ~10 |
| **Total** | | **~100–120 documents** |

This is large enough to demonstrate cross-reference handling but small enough to curate properly and build high-quality evaluation data.

### Secondary: EFSA Guidance Documents

EFSA publishes detailed scientific guidance for each regulatory area (e.g., guidance on novel food dossier preparation, guidance on food contact material safety assessment). These are freely downloadable PDFs that explain how to interpret and apply the regulations. Including them adds a "practical interpretation" layer beyond the raw legal text.

### Tertiary: Published Compliance Checklists (for evaluation)

Multiple sources publish structured compliance checklists that serve as ground truth:
- **EFSA application guidance** documents contain explicit requirement lists ("your dossier must contain...")
- **Food safety consulting firms** (SGS Digicomply, Biosafe, Quality Smart Solutions) publish summary regulatory guides with structured requirement lists
- **European Parliament fact sheets** on food safety provide structured overviews of the regulatory framework
- **Academic papers** on EU food law sometimes include requirement taxonomies

These become our evaluation ground truth (see Section 7).

---

## 5. What the System Builds

### Phase 0: Corpus Entity Extraction (Offline, Run Once)

Before the system can serve any queries, we parse the entire corpus and extract every entity the regulations mention. This is a substantial data engineering + NLP pipeline that runs offline and produces the structured indexes that power the application.

**What gets extracted:**

| Entity type | Examples | Source regulations |
|---|---|---|
| **Product categories** | "novel food," "food supplement," "infant formula," "food for special medical purposes" | Reg. 2015/2283, Reg. 609/2013, Dir. 2002/46/EC |
| **Ingredient categories** | "food additive," "flavouring," "enzyme," "novel food ingredient," "GMO" | Reg. 1333/2008, Reg. 1334/2008, Reg. 1332/2008, Reg. 2015/2283, Reg. 1829/2003 |
| **Specific regulated substances** | Named additives (E-numbers), authorised novel food ingredients, permitted vitamins/minerals | Reg. 1333/2008 annexes, Union List of novel foods, Reg. 1170/2009 |
| **Claim types** | "health claim," "nutrition claim," "reduction of disease risk claim" | Reg. 1924/2006 |
| **Packaging/contact material types** | "plastic," "recycled plastic," "active/intelligent materials," "ceramic" | Reg. 10/2011, Reg. 2022/1616, Dir. 84/500/EEC |
| **Labelling elements** | "allergen declaration," "nutrition declaration," "origin labelling," "date marking" | Reg. 1169/2011 |
| **EU member states** | All 27, plus EEA (where national transposition varies) | Cross-cutting |

**How it works:**
1. Parse EUR-Lex XML → structured articles (same as chunking pipeline)
2. For each regulation, extract defined terms from "Definitions" articles (almost every regulation has an Article 2 or 3 that defines its key terms)
3. Extract annexes (which contain the actual lists: authorised additives, permitted substances, etc.)
4. Use LLM-assisted extraction for the long tail of terms not in formal definitions (with human validation)
5. Build a **regulatory domain mapping**: `{entity} → {list of applicable regulation CELEX numbers + specific articles}`

**Output:** A set of JSON indexes that become both the dropdown options in the UI AND the deterministic routing table for retrieval.

**Why this matters for the portfolio:** This step is arguably more impressive than the RAG itself. It demonstrates:
- Corpus-level understanding (not just "throw it in a vector store")
- Data engineering on structured XML
- LLM-assisted entity extraction with validation
- Domain modelling (mapping entities to regulatory scopes)

### Architecture (Runtime)

```
┌───────────────────────────────────────────────────────────┐
│                  Structured Input (UI)                      │
│                                                             │
│  Product category:    [Novel food          ▼]               │
│  Ingredients:         [☑ Insect protein] [☑ Whey] [☐ ...]  │
│  Target market:       [Germany             ▼]               │
│  Packaging:           [Plastic             ▼]               │
│  Claims:              [☑ High protein] [☐ Organic] [☐ ...] │
│                                                             │
│  All options derived from corpus entity extraction.         │
│  User can also type free-text ingredients (matched against  │
│  the extracted index, with "unknown ingredient" flagged).   │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│           Deterministic Routing (no LLM)                   │
│                                                             │
│  Input selections → lookup in regulatory domain mapping:    │
│    "novel food" → Reg. 2015/2283, Impl. 2017/2468-2469    │
│    "insect protein" → Novel food Union List                 │
│    "high protein claim" → Reg. 1924/2006 Art. 8            │
│    "plastic packaging" → Reg. 10/2011                       │
│    "Germany" → flag any DE-specific transposition           │
│    (always included) → Reg. 1169/2011 (labelling)          │
│    (always included) → Reg. 178/2002 (general food law)    │
│                                                             │
│  Output: targeted list of CELEX numbers + article ranges    │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│           Targeted Retrieval (vector store)                 │
│                                                             │
│  Retrieve articles from ONLY the regulations identified     │
│  by the routing step. Metadata filter on CELEX number.      │
│  Semantic search within those articles for the specific     │
│  product/ingredient context.                                │
│                                                             │
│  Much smaller search space than "search everything" →       │
│  higher precision, lower cost, faster.                      │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│        Cross-Reference Resolution                          │
│                                                             │
│  Follow "as amended by" and "see also" links.              │
│  Metadata graph: regulation → articles → amendments        │
│  (Hybrid: metadata lookup + LLM for ambiguous refs)        │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│        Structured Extraction (LLM)                         │
│                                                             │
│  THIS is where the LLM earns its keep.                     │
│  For each relevant regulation/article, extract:            │
│  - regulation_id (CELEX number)                            │
│  - article_number                                          │
│  - requirement_summary (plain English)                     │
│  - requirement_type (labelling | safety_assessment |       │
│    authorisation | max_limit | notification | ...)         │
│  - applicable_product_categories                           │
│  - deadline_or_timeline (if any)                           │
│  - penalty_reference (if stated)                           │
│  - cross_references (list of related CELEX numbers)        │
│  - confidence_score                                        │
└───────────────┬───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│           Compliance Checklist Output                       │
│                                                             │
│  Structured JSON + human-readable summary                   │
│  Grouped by: must-do-before-launch / ongoing /              │
│              if-applicable                                   │
│  Each item: requirement + source citation + confidence      │
└───────────────────────────────────────────────────────────┘
```

### Why This Architecture, Not the "Chat" Alternative

The naive approach — free-text query → LLM parses intent → retrieval — is the default in every RAG tutorial. We reject it deliberately:

| | Free-text query + LLM parsing | Structured input + deterministic routing |
|---|---|---|
| **Input reliability** | LLM must guess product type, ingredients, market from ambiguous text. Failure mode: misparses → wrong regulations retrieved. | User selects from corpus-derived options. Zero ambiguity. |
| **Evaluation reproducibility** | Same query phrased differently → different results. Hard to build reproducible test suites. | `(category=X, ingredient=Y, market=Z)` → deterministic. Fully reproducible evaluation. |
| **Cost per query** | Extra LLM call for query analysis. | Zero LLM cost for input processing. |
| **Retrieval precision** | Searches entire vector store. Broader, noisier. | Searches only the regulations the routing table identifies. Narrower, more precise. |
| **Demonstrates** | "I can call an LLM API" (everyone can). | "I built a structured domain model from a regulatory corpus" (almost nobody does). |

The LLM is used only in the extraction step — the one place where language understanding is genuinely required and where traditional methods fall short.

### LangChain Components (Used Naturally)

| Component | Purpose | Why it's the right tool |
|---|---|---|
| **Document loaders** | Load EUR-Lex HTML/XML documents | Handles structured legal documents with article/section hierarchy |
| **Text splitters** | Chunk regulatory text preserving article boundaries | Legal text must be chunked at article boundaries, not arbitrary character counts — this is a non-trivial design decision worth documenting |
| **Vector store (Chroma or FAISS)** | Semantic retrieval within routed regulation subsets | Standard retrieval backbone, but used with metadata filtering to restrict search scope |
| **Structured output parsers (Pydantic)** | Force LLM output into typed compliance requirement schema | The structured extraction schema IS the product — this isn't cosmetic |
| **Metadata filtering** | Filter by regulation CELEX number, article range, in-force status | The routing table outputs CELEX numbers; the vector store filters on them |
| **Chains** | Orchestrate retrieval → cross-reference → extraction → assembly | Simpler chain than before — no query analysis step needed |

### What this is NOT

- Not a chatbot. No conversation, no open-ended dialogue. Input: structured product parameters. Output: structured compliance checklist.
- Not a "natural language query" system. The input is deliberately structured because structured input is more reliable, more reproducible, and cheaper than LLM-parsed free text.
- Not a legal advice tool. Every output carries a disclaimer and confidence scores. The tool identifies *which regulations are likely relevant* — a human compliance expert validates.
- Not trying to index all EU law. The food safety focus is deliberate and stated.

---

## 6. Technical Challenges Worth Documenting

These are the hard problems that make this project portfolio-worthy (not just another RAG tutorial):

### 6a. Corpus Entity Extraction and Domain Modelling

The upfront task of extracting every regulated entity from ~120 legal documents is itself a significant NLP + data engineering challenge. EU regulations define terms in various ways:

- **Formal definitions** in dedicated articles (e.g., Article 3 of Reg. 2015/2283 defines "novel food" across seven sub-categories)
- **Annexes with structured lists** (e.g., the Union List of authorised novel foods, the list of permitted additives by E-number in Reg. 1333/2008)
- **Inline references** scattered through operative articles ("foods intended for infants and young children as defined in...")
- **Cross-regulation definitions** ("for the purposes of this Regulation, the definitions in Article 2 of Regulation (EC) No 178/2002 shall apply")

**Approach:** Hybrid extraction pipeline:
1. Rule-based extraction for "Definitions" articles and structured annexes (these follow predictable patterns)
2. LLM-assisted extraction for inline references and implicit scope definitions
3. Human validation of the resulting entity index (this is a bounded task — ~120 documents, not millions)
4. Build the regulatory domain mapping: `{entity} → [(CELEX, article_range), ...]`

**Blog-worthy insight:** "I extracted every regulated food entity from 120 EU legal acts. Here's what the regulatory domain graph looks like."

### 6b. Chunking Strategy for Legal Text

Standard RAG tutorials chunk by character count or sentence. Legal text has a rigid hierarchy: Regulation → Chapter → Section → Article → Paragraph → Subparagraph. Chunking must respect this structure because:
- An article is the atomic unit of a legal obligation
- Cross-references point to specific articles, not character offsets
- Retrieving half an article is worse than useless — it can be misleading

**Approach:** Parse EUR-Lex XML structure to extract articles as individual chunks. Each chunk carries metadata: CELEX number, article number, chapter title, in-force date, amendment history. Longer articles get sub-chunked at paragraph level with parent article context preserved.

**Blog-worthy insight:** "Why character-count chunking fails for legal text, and what to do instead."

### 6c. Deterministic Routing vs. Semantic Search

Most RAG systems search the entire corpus for every query. We search only the regulations that the routing table identifies as relevant to the user's structured input. This is a design decision with measurable consequences:

- **Precision improvement:** Searching 5 regulations instead of 120 eliminates false matches from unrelated domains
- **Cost reduction:** Fewer chunks retrieved → fewer tokens sent to the LLM for extraction
- **Testability:** Routing is deterministic and independently testable — we can unit-test "does selecting 'novel food' + 'insect protein' route to the correct CELEX numbers?" without involving the LLM at all

**The interesting edge case:** What happens when a user selects an ingredient that isn't in our extracted index? The system flags it as "unknown — not found in the current regulatory entity index" and falls back to semantic search across the full corpus. This fallback path is separately evaluated.

### 6d. Cross-Reference Resolution

EU regulations constantly refer to each other: "as defined in Article 3(2) of Regulation (EC) No 178/2002" or "in accordance with the procedure laid down in Article 5 of Regulation (EU) 2015/2283." A system that retrieves one regulation but misses the cross-reference delivers an incomplete answer.

**Approach:** Build a lightweight metadata graph (not a full knowledge graph — that's scope creep) from EUR-Lex structured metadata. Each document has a list of documents it references (available in Cellar metadata). When the extraction step identifies a cross-reference, the system can look up the referenced article and include it in context. This is a hybrid approach: metadata graph for known references, LLM for ambiguous textual references.

**Blog-worthy insight:** "The hidden dependency graph in EU legislation, and why RAG alone isn't enough."

### 6e. Structured Extraction at Scale

Extracting a Pydantic-typed compliance requirement from dense legal text is harder than extracting entities from news articles. Legal language is intentionally precise but verbose. Nested conditions ("unless the product falls within the scope of Regulation X, in which case Article Y applies, except where...") require the LLM to reason, not just extract.

**Approach:** Define a `ComplianceRequirement` Pydantic model. Use few-shot prompting with manually validated examples. Include confidence scoring (the LLM rates its own extraction confidence, which we validate against ground truth).

### 6f. Handling "Not Applicable"

A critical capability: the system must be able to say "this regulation does not apply to your product" — and do so correctly. With deterministic routing, this is partially solved at the input stage (if you didn't select "organic," organic regulations aren't routed). But within a routed regulation, not every article applies to every product. False positives (flagging irrelevant requirements) waste compliance team time. False negatives (missing an applicable requirement) create legal risk. This asymmetry should be documented and measured.

---

## 7. Evaluation Framework

This is where the project separates from every other "legal RAG" on GitHub. The structured-input architecture makes evaluation cleaner because each step is independently testable. Evaluation has five layers:

### Layer 0: Entity Extraction Completeness

**Question:** Did the corpus entity extraction capture all regulated entities?

**Metric:** Coverage rate against a manually compiled reference list.

**Ground truth construction:**
- For 3 well-documented regulatory areas (novel foods, food additives, FIC labelling), manually compile a complete list of defined entities from the source regulations
- Compare against the automatically extracted entity index
- Measure: what percentage of reference entities were captured?

**Target:** Coverage > 90% for the 3 reference areas. Document the types of entities missed (e.g., implicit definitions, cross-regulation definitions).

### Layer 1: Routing Accuracy

**Question:** Given a set of structured user inputs, does the deterministic routing correctly identify the applicable regulations?

**Metric:** Precision and recall of routed CELEX numbers against manually determined applicable regulations.

**Ground truth construction:**
- Select 20–30 product scenarios (e.g., "novel food with insect protein + plastic packaging + health claim," "organic baby formula + glass packaging," "conventional ready meal + nutrition claims")
- For each scenario, manually identify the applicable regulations (using EFSA guidance and published compliance guides)
- Run the routing step and compare

**Target:** Routing recall > 95% (this step should almost never miss an applicable regulation — it's a lookup, not a prediction). Routing precision > 80% (some over-inclusion is acceptable; the extraction step filters further).

**Why this is powerful:** This layer is fully deterministic, requires zero LLM calls, and can run as a unit test suite in CI/CD. If routing fails, everything downstream fails — catching it here is cheap.

### Layer 2: Retrieval Quality (Within Routed Regulations)

**Question:** Within the correctly routed regulations, does semantic retrieval surface the right articles?

**Metric:** Recall@K and Precision@K on (scenario, relevant_articles) pairs.

**Ground truth construction:**
- For the same 20–30 scenarios, identify not just the applicable regulations but the specific articles within them
- Measure whether retrieval surfaces those articles

**Target:** Recall@10 > 85%.

### Layer 3: Extraction Accuracy

**Question:** Given the correct regulatory text, does the system extract the right compliance requirements?

**Metric:** Precision and recall of extracted requirements against expert-validated checklists.

**Ground truth construction:**
- For 10 well-documented regulatory areas (e.g., novel food application requirements, FIC labelling requirements), compile a complete checklist from EFSA guidance documents
- Run the system on queries that should trigger each checklist
- Score: how many checklist items did the system extract (recall)? How many extracted items were actually in the checklist (precision)?

**Target:** Precision > 80%, Recall > 75%.

### Layer 3: End-to-End Scenario Testing

**Question:** For a complete product scenario, does the system produce a correct and complete compliance checklist?

**Method:** Select 5 scenarios. For each:
1. Run the full pipeline
2. Compare output against a manually compiled "gold standard" checklist
3. Classify each system output item as: correct, partially correct, incorrect, or hallucinated
4. Classify each gold standard item as: found by system, or missed

**Presentation:** Confusion-matrix-style results table per scenario, plus aggregated scores.

### Layer 4: Failure Mode Analysis

**Question:** When the system fails, HOW does it fail?

**Categories:**
- **Entity extraction gap:** A regulated entity isn't in the index, so it can't be selected and can't be routed (corpus coverage issue)
- **Routing miss:** User input should have triggered a regulation but the mapping table doesn't include the link (domain modelling issue)
- **Retrieval failure:** Correct regulation routed but the right article not retrieved (chunking issue? embedding issue?)
- **Extraction failure:** Correct text retrieved but requirement not extracted (prompt issue? legal language complexity?)
- **Hallucination:** System invents a requirement not in the source text
- **Cross-reference miss:** System identifies a regulation but misses a critical amendment or exception
- **Scope error:** System applies a requirement to a product it doesn't cover (false positive within a correctly routed regulation)

**Presentation:** Error breakdown by category with specific examples. This is the section hiring managers remember.

---

## 8. Deployment Plan

### Streamlit App (Primary)

A Streamlit application with two main areas:

**Input panel (left/top):** Structured product scenario form — all options populated from the corpus entity extraction:
- Product category (dropdown: values extracted from regulation scope definitions)
- Ingredients (multi-select with search: every ingredient/ingredient category found in the corpus, grouped by regulatory domain. Free-text fallback for unlisted ingredients, which triggers the semantic search fallback path and flags "not found in regulatory index")
- Target market (dropdown: 27 EU member states + EEA)
- Packaging type (dropdown: material types from food contact material regulations)
- Claims (multi-select: claim types from Reg. 1924/2006)
- Optional: product intended for specific population (infants, medical purposes, etc.)

**Results panel (centre/bottom):** Compliance checklist output
- Grouped by: **must-do-before-launch** / **ongoing obligations** / **if-applicable**
- Each requirement shows: plain-English summary, source regulation + article, confidence score
- Expandable: click to see the source regulatory text with the relevant passage highlighted
- Every item links to the EUR-Lex source URL
- Sidebar: routing transparency ("These regulations were selected because you indicated: novel food + insect protein + health claim + plastic packaging")

**Design goal:** A hiring manager opens the app, selects a few dropdowns, clicks "Generate checklist," and sees a structured, cited compliance report in 10–15 seconds. No prompt engineering required. No "how should I phrase my question?" friction.

### Docker + Render (Production)

- `Dockerfile` using `python:3.11-slim`
- Environment variables for API keys (OpenAI or Anthropic)
- Vector store + entity indexes baked into the image (or mounted volume)
- Deploy to Render free tier for a live demo URL
- Health check endpoint at `/health`

### FastAPI Endpoint (Secondary)

A `/compliance-check` endpoint that accepts a product scenario as structured JSON and returns the compliance checklist. Same structured input contract as the UI — no free text.

```
POST /compliance-check
{
  "product_category": "novel_food",
  "ingredients": ["insect_protein_cricket", "whey_protein", "cocoa_butter"],
  "target_market": "DE",
  "packaging": "plastic",
  "claims": ["high_protein"],
  "specific_population": null
}

→ 200 OK
{
  "routed_regulations": ["32015R2283", "32017R2469", "31924R2006", "32011R0010", "32011R1169"],
  "requirements": [
    {
      "regulation_id": "32015R2283",
      "article": "Art. 3(2)(a)(iv)",
      "requirement_summary": "Insects and their parts are classified as novel foods requiring authorisation before placing on the EU market.",
      "requirement_type": "authorisation",
      "priority": "must_do_before_launch",
      "confidence": 0.92,
      "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015R2283",
      "cross_references": ["32017R2470"]
    },
    ...
  ],
  "unknown_ingredients": [],
  "fallback_search_used": false
}
```

A `/entities` endpoint that returns the available options for each input field (useful for programmatic integrations and for documenting what the system covers):

```
GET /entities/ingredients

→ 200 OK
{
  "ingredients": [
    {"id": "insect_protein_cricket", "label": "Cricket protein (Acheta domesticus)", "regulatory_domain": "novel_food", "source_regulation": "32015R2283"},
    {"id": "whey_protein", "label": "Whey protein", "regulatory_domain": "general", "source_regulation": null},
    ...
  ]
}
```

---

## 9. Project Structure

```
eu-food-regulatory-intelligence/
├── README.md                          # Business-first, < 500 words
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .gitignore
├── .env.example
│
├── data/
│   ├── raw/                           # EUR-Lex XML downloads (gitignored)
│   ├── processed/                     # Parsed articles as JSON
│   ├── indexes/                       # Entity indexes + routing tables (checked in)
│   │   ├── entities.json              # All extracted entities with metadata
│   │   ├── routing_table.json         # entity → [CELEX + article_range] mapping
│   │   └── cross_references.json      # Regulation dependency graph
│   ├── evaluation/                    # Ground truth checklists
│   └── sample/                        # Small sample for reviewers to run
│
├── src/
│   ├── ingestion/
│   │   ├── eurlex_downloader.py       # SPARQL queries + REST API calls
│   │   ├── xml_parser.py              # Formex XML → structured articles
│   │   └── metadata_graph.py          # Cross-reference graph builder
│   ├── indexing/
│   │   ├── entity_extractor.py        # Extract regulated entities from corpus
│   │   ├── definition_parser.py       # Rule-based extraction from "Definitions" articles
│   │   ├── annex_parser.py            # Structured extraction from annexes (lists, tables)
│   │   ├── llm_entity_extractor.py    # LLM-assisted extraction for implicit definitions
│   │   ├── routing_table_builder.py   # Build entity → regulation mapping
│   │   └── validate_index.py          # Validation against manual reference lists
│   ├── retrieval/
│   │   ├── chunking.py                # Article-aware chunking strategy
│   │   ├── embeddings.py              # Embedding + vector store setup
│   │   └── router.py                  # Deterministic routing from user input to CELEX numbers
│   ├── extraction/
│   │   ├── schemas.py                 # Pydantic models for requirements
│   │   ├── extractor.py               # LLM structured extraction chain
│   │   └── cross_ref_resolver.py      # Follow cross-references
│   ├── pipeline.py                    # End-to-end orchestration
│   └── api.py                         # FastAPI endpoints (/compliance-check, /entities)
│
├── app/
│   └── streamlit_app.py               # Streamlit UI with structured dropdowns
│
├── evaluation/
│   ├── build_ground_truth.py          # Scripts to compile checklists
│   ├── eval_entity_coverage.py        # Entity extraction completeness
│   ├── eval_routing.py                # Routing accuracy (deterministic, no LLM)
│   ├── eval_retrieval.py              # Retrieval metrics within routed regulations
│   ├── eval_extraction.py             # Extraction precision/recall
│   ├── eval_e2e.py                    # End-to-end scenario testing
│   └── failure_analysis.py            # Categorise and document failures
│
├── notebooks/
│   ├── 01_data_exploration.ipynb      # Corpus statistics, document structure
│   ├── 02_entity_extraction.ipynb     # Entity extraction development + validation
│   ├── 03_chunking_experiments.ipynb  # Compare chunking strategies
│   ├── 04_retrieval_experiments.ipynb  # Embedding models, retrieval params
│   └── 05_results_analysis.ipynb      # Evaluation results + visualisations
│
├── tests/
│   ├── test_parser.py
│   ├── test_entity_extraction.py
│   ├── test_routing.py                # Deterministic routing unit tests
│   ├── test_chunking.py
│   ├── test_extraction.py
│   └── test_pipeline.py
│
└── docs/
    ├── architecture.md                # Architecture diagram + design decisions
    ├── entity_index.md                # What entities were extracted, coverage stats
    ├── chunking_strategy.md           # Deep dive on legal text chunking
    └── evaluation_results.md          # Full results + failure analysis
```

---

## 10. Communication Plan

### README Structure (< 500 words)

1. **One-liner:** "Automated compliance checklist generation for EU food safety regulations — structured input, deterministic routing, LLM extraction with cited sources."
2. **The problem:** Companies spend €300-500/hour on regulatory consultants to answer "what do I need to comply with?"
3. **What this builds:** A system that takes structured product parameters (category, ingredients, market, packaging, claims) and returns a structured compliance checklist. Entities extracted from the corpus itself populate the input options. Deterministic routing identifies applicable regulations. LLM extraction produces cited, confidence-scored requirements.
4. **Key results:** Entity coverage, routing accuracy, retrieval recall, extraction precision/recall, number of scenarios tested. (Numbers filled in after evaluation.)
5. **Try it:** Link to deployed Streamlit app.
6. **Tech stack:** Python, LangChain, Chroma/FAISS, OpenAI/Anthropic, Streamlit, FastAPI, Docker.
7. **How to run:** `docker compose up` or `pip install -e . && python -m src.pipeline`.

### Blog Post Outline

**Title:** "Why I Rejected the Chatbot Pattern: Building a Compliance Intelligence System Over EU Food Safety Law"

1. **Hook:** "I needed to figure out if I could sell cricket flour protein bars in Germany. The answer is spread across 15 different legal acts. So I built a system to extract every regulated entity from 120 EU food safety regulations and route queries deterministically — no LLM needed until the actual hard part."
2. **The entity extraction problem:** Parsing 120 legal acts to build a structured index of every regulated product category, ingredient, claim type, and packaging material. Why this is harder than it sounds (formal definitions, annex tables, inline references, cross-regulation definitions).
3. **Why I didn't build a chatbot:** The case for structured input + deterministic routing over free-text query + LLM parsing. Measurable benefits: reproducibility, precision, cost, testability.
4. **Where the LLM actually adds value:** Structured extraction from dense legal prose. Pydantic schemas, few-shot prompting, confidence scoring.
5. **Evaluation: the part nobody does:** Five layers of evaluation from entity coverage to end-to-end scenarios. How I built ground truth from EFSA guidance documents. Where the system fails and why.
6. **What I'd do next:** Full knowledge graph for cross-references, active learning from compliance expert feedback, extension to other regulatory domains (medical devices, cosmetics).

**Publish on:** Medium/TDS + LinkedIn.

### Interview Talking Points (STAR Format)

**S:** Companies launching food products in the EU face a complex regulatory landscape spanning hundreds of legal acts that cross-reference each other. Consultants charge €300–500/hour to manually answer "what do I need to comply with?"

**T:** Build a system that takes structured product parameters and automatically identifies all applicable regulations, extracting structured compliance requirements with cited sources.

**A:** First, I parsed ~120 EUR-Lex food safety regulations and extracted every regulated entity — product categories, ingredient classes, claim types, packaging materials — building a structured index and a deterministic routing table. This meant the system routes user inputs to the correct regulations without an LLM, making routing independently testable and reproducible. Then I built a RAG pipeline with article-aware chunking over the routed regulation subset, using Pydantic-structured LLM extraction for the actual compliance requirements. Evaluated across five layers: entity coverage, routing accuracy, retrieval quality, extraction precision/recall, and end-to-end scenario testing against expert-compiled checklists. Deployed as a Streamlit app with Docker.

**R:** Achieved [X]% routing recall (deterministic, no LLM), [X]% retrieval recall within routed regulations, and [X]% extraction precision. Identified that cross-reference misses were the primary failure mode ([X]% of errors), which led to building a metadata graph for regulatory dependencies. The entity extraction step itself surfaced [N] regulated entities across [M] regulatory domains — this index became both the UI and the test suite.

---

## 11. Scope and Timeline

### MVP (Week 1-2): Corpus Ingestion + Entity Extraction

- [ ] Download and parse food safety corpus from EUR-Lex (50 core regulations)
- [ ] Implement article-aware chunking
- [ ] Extract entities from "Definitions" articles and structured annexes (rule-based)
- [ ] LLM-assisted extraction for implicit definitions
- [ ] Build routing table: entity → [CELEX + article_range]
- [ ] Validate entity index against 3 reference regulatory areas
- [ ] Build vector store with metadata
- [ ] 5 evaluation scenarios: test routing accuracy only (no LLM extraction yet)

### Iteration 1 (Week 3): Retrieval + Extraction Pipeline

- [ ] Implement deterministic router (structured input → CELEX numbers)
- [ ] Implement metadata-filtered retrieval within routed regulations
- [ ] Build structured extraction chain (Pydantic schemas, few-shot prompts)
- [ ] Build metadata graph from EUR-Lex cross-reference data
- [ ] Implement cross-reference resolver
- [ ] Expand corpus to ~120 documents, update entity index
- [ ] Run evaluation layers 0–3 on 20 scenarios

### Iteration 2 (Week 4): Deployment + Polish

- [ ] Build Streamlit app with entity-driven dropdowns
- [ ] Build FastAPI endpoints (/compliance-check, /entities)
- [ ] Dockerise
- [ ] Deploy to Render
- [ ] Full evaluation (30 scenarios, all 5 layers)
- [ ] Failure mode analysis

### Communication (Week 5): Write-Up

- [ ] Write README
- [ ] Write blog post
- [ ] Record 2-min demo video (screen capture of Streamlit app)
- [ ] Prepare interview talking points
- [ ] Final code cleanup: docstrings, type hints, linting, tests

### Total: 5 weeks

---

## 12. Estimated Costs

| Item | Cost |
|---|---|
| EUR-Lex data access | Free (public data, EU Login required for bulk download) |
| OpenAI API (embedding + extraction) | ~$10–20 for development + evaluation |
| Anthropic API (alternative) | ~$10–20 |
| Render deployment | Free tier |
| Vector store | Local (Chroma/FAISS), no cost |
| **Total** | **~$20–40** |

---

## 13. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| EUR-Lex XML parsing is more complex than expected | Medium | Medium | Start with HTML full-text (simpler); fall back to PDF extraction via `pymupdf` if XML is too painful. Existing `eurlex-toolbox` handles Formex XML. |
| Evaluation ground truth is hard to compile | Medium | High | Start with the best-documented areas (novel foods, FIC labelling) where EFSA publishes explicit requirement lists. Limit initial evaluation to these. |
| LLM hallucination on legal text | High | High | Confidence scoring + source citation for every extracted requirement. Failure analysis explicitly categorises hallucinations. Disclaimer in all outputs. |
| Scope creep into "all EU law" | Medium | Medium | Hard-scope to food safety from day 1. The README and blog explain this is deliberate. |
| Cross-reference resolution is too hard | Medium | Medium | MVP works without it (baseline). Iteration 1 adds it. If metadata approach insufficient, document it as a known limitation and future work. |

---

## 14. References and Prior Art to Cite

- **GraphCompliance** (arXiv, Oct 2025): KG-based LLM framework for GDPR compliance. Validates the problem space. Our approach is simpler (metadata graph, not full KG) and domain-specific.
- **Chat-EUR-Lex** (Aptus-AI, 2023-24): Basic RAG chatbot over EUR-Lex. We differentiate through structured extraction, domain focus, and evaluation.
- **EUR-Lex-Sum dataset**: Multilingual summarisation benchmark for EU legal acts. Demonstrates academic interest in EUR-Lex NLP.
- **eurlex R package** (Ovádek, 2021): Facilitating access to data on EU laws. Published in Political Research Exchange. Validates that EUR-Lex data access is a known challenge worth solving.
- **EUR-Lex multi-label classification** (57K docs, EUROVOC labels): Shows EUR-Lex is used for NLP research but classification is a different task from compliance extraction.

---

## 15. Checklist (From Portfolio Principles Reference)

### Business Framing
- [x] Clear business question in first sentence
- [x] Identified stakeholder (food companies launching products in EU)
- [x] Quantified cost of current solution (€300-500/hour consulting)
- [x] Specific, actionable output (structured compliance checklist)

### Technical Execution
- [x] Real-world data (EUR-Lex, EFSA guidance)
- [x] Multiple data sources (EUR-Lex regulations + EFSA guidance + compliance checklists)
- [x] Substantial data engineering (XML parsing, entity extraction, routing table construction, article-aware chunking, metadata graph)
- [x] Appropriate technique (deterministic routing + targeted RAG + structured extraction — each step justified by the task)
- [x] Multi-layered evaluation framework (5 layers, independently testable)
- [x] Honest limitation documentation planned

### Modern Stack
- [x] Evaluation framework for LLM outputs (precision/recall/failure modes across 5 layers)
- [x] Cost analysis planned (API costs per query — lower than chat approach due to targeted retrieval)
- [x] Failure mode documentation (7 categorised error types)
- [x] Comparison against baselines (full-corpus search vs. routed retrieval, with and without cross-reference resolution)

### Deployment & Engineering
- [x] Interactive demo (Streamlit app)
- [x] API endpoint (FastAPI)
- [x] Docker + cloud deployment (Render)
- [x] Professional code structure (src/, tests/, docs/)
- [x] Version control with meaningful commits planned

### Communication
- [x] README plan (< 500 words, business-first)
- [x] Blog post outline
- [x] Resume line drafted
- [x] Interview talking points (STAR format)
- [x] Architecture diagram included

### Novelty
- [x] Searched GitHub, Kaggle, Medium, arXiv
- [x] Framing distinct from existing projects (food safety + structured extraction + evaluation)
- [x] Not replicable by following a tutorial
- [x] Prior art acknowledged and differentiation stated

---

*This document is the complete plan for L1. Implementation begins with the MVP scope (Weeks 1-2).*
