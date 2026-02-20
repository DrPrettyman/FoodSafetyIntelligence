# Modern Framework Portfolio Project Ideas

## Context

The existing portfolio has two "classical" data science projects:
1. **Steam Game Market Intelligence Engine** — recommendation systems, market gap analysis, multi-API pipeline
2. **CPG Private Label Opportunity Engine** — competitive analysis, nutritional gap scoring, multi-source scraping + bulk data

Both demonstrate strong business thinking, end-to-end pipelines, and quantified impact. What's missing: anything involving modern ML/AI frameworks (PyTorch, TensorFlow, LangChain) that many job descriptions now explicitly require.

**Guiding principle (from the article):** "Trendy library usage" is listed as something hiring managers DON'T care about. The technology must be a natural consequence of the business problem, not the starting point. Every idea below is framed as a business problem first, with the framework appearing because it's the right tool.

---

## LangChain Project Ideas

### Idea L1: EU Regulatory Intelligence Engine

**Business question:** "For a company launching product X in market Y, which EU regulations apply, what are the specific compliance requirements, and what are the deadlines and penalties?"

**Who pays for this today:** Regulatory consulting firms (€300-500/hour), legal compliance SaaS (Ascent, RegTech), in-house compliance teams at any company selling into EU markets.

**Data source:** EUR-Lex — the official database of EU law. Every regulation, directive, and decision is freely downloadable as structured XML/HTML. Thousands of documents, continuously updated. Also available: national transposition measures, case law from CJEU.

**What the project builds:**
- RAG system over the full EUR-Lex corpus (or a focused subset, e.g., food safety regulations, which ties nicely to the Private Label project's domain)
- Structured extraction: for each query, return not just text but structured output (regulation ID, article number, requirement summary, deadline, applicable member states, penalty range, related regulations)
- Multi-step reasoning: "Does this product need CE marking?" requires finding the applicable directive, checking product categories, and cross-referencing harmonised standards
- Evaluation against known compliance checklists (e.g., published GDPR compliance checklists, EU AI Act requirement summaries)

**LangChain components used naturally:**
- Document loaders + text splitters for EUR-Lex corpus
- Vector store (FAISS/Chroma) for retrieval
- Structured output parsers for compliance requirement extraction
- Chains or agents for multi-step regulatory reasoning
- Potentially tool use (search EUR-Lex API for latest amendments)

**Pros:**
- Genuine business problem — companies spend millions on regulatory compliance
- Verifiable outputs — compliance requirements are factual and checkable
- Ties to EU/European focus of the other portfolio projects
- Could narrow scope to food safety regulation, connecting directly to the Private Label project
- Corpus is structured, well-maintained, and freely available
- Interesting evaluation challenge: how do you measure whether an LLM correctly identified all applicable regulations?

**Cons:**
- Legal domain is intimidating — easy to get out of depth if scope isn't carefully controlled
- Risk of looking like a generic "RAG over documents" project if not framed sharply
- Evaluation ground truth may be hard to construct beyond simple cases
- Regulatory text is dense and cross-referential — chunking strategy is non-trivial (this is actually a pro for the portfolio, but a con for development time)

**Novelty check needed:** Are there existing portfolio projects doing RAG over EUR-Lex? Over regulatory corpora in general?

**Estimated scope:** 4-5 weeks

---

### Idea L2: Earnings Call Intelligence Extractor

**Business question:** "Across the last N quarters of earnings calls from companies in sector X, what are the emerging risk themes, who's gaining/losing confidence, what specific forward guidance numbers were given, and which competitors were mentioned?"

**Who pays for this today:** Bloomberg Terminal (specific features for earnings analysis), equity research analysts at investment banks, financial data providers (Refinitiv, S&P Capital IQ), hedge fund quant teams.

**Data source:** Earnings call transcripts are freely available from multiple sources:
- SEC EDGAR (10-K, 10-Q filings with MD&A sections)
- Financial Modeling Prep API (free tier, earnings call transcripts)
- Seeking Alpha (transcripts, though may require scraping)
- Motley Fool Transcripts

**What the project builds:**
- Pipeline that ingests earnings call transcripts for a sector (e.g., European banks, or tech companies)
- Structured extraction per call: reported numbers, forward guidance (specific figures + language confidence), risk mentions (categorised), competitor mentions, sentiment shifts vs. previous quarter
- Cross-call analysis: aggregate extracted signals to identify sector-level trends, divergence between companies, and leading indicators
- Evaluation: compare extracted guidance numbers against actual subsequent reported numbers; compare extracted sentiment against stock price reaction (not as prediction, but as validation of extraction quality)

**LangChain components used naturally:**
- Document loaders for transcript ingestion
- Extraction chains with structured output (JSON schema for guidance, risks, sentiment)
- Potentially map-reduce chains for summarising across many transcripts
- Tool use for looking up actual reported numbers to validate extracted guidance
- Vector store for cross-referencing mentions across calls

**Pros:**
- Very clear business value — analysts spend 2-4 hours per transcript manually
- Outputs are verifiable (extracted numbers can be checked against databases)
- Financial domain is high-value and relevant to target companies (Revolut, Clarity AI)
- Rich evaluation story: precision/recall on number extraction, sentiment accuracy vs. market reaction
- Can demonstrate scaling: 10 transcripts → 100 → 1000, showing how the pipeline handles volume
- Strong interview talking points: structured extraction, evaluation methodology, financial domain knowledge

**Cons:**
- Financial NLP is a somewhat crowded space — need to verify the specific framing is novel
- Earnings call transcripts may have copyright/terms-of-use restrictions depending on source
- Stock price correlation analysis could look like "stock prediction" if not framed carefully (it's validation of extraction, not prediction)
- US-centric if using SEC EDGAR — may not align with EU focus of other projects (though European companies with ADRs file with SEC too)

**Novelty check needed:** Are there existing portfolio projects doing structured extraction from earnings calls with LangChain? Financial NLP is popular but the specific "sector intelligence report" framing may be novel.

**Estimated scope:** 4-5 weeks

---

## PyTorch Project Ideas

### Idea P1: Domain-Specific Document Classifier — Fine-Tune vs. Prompt Benchmark

**Business question:** "For high-volume text classification in domain X, should we fine-tune a small model or pay for LLM API calls? At what volume does fine-tuning break even, and what accuracy do we sacrifice?"

**Who pays for this today:** Every ML team deploying NLP in production faces this decision. AWS, Google Cloud, and Azure all offer fine-tuning services. MLOps consultancies advise on build-vs-buy.

**Data source candidates (all freely available, pre-labelled):**
- **CFPB Consumer Complaints Database:** Millions of consumer financial complaints, each labelled with product category, issue type, and company. Updated daily. Free download from data.gov.
- **PubMed abstracts with MeSH headings:** Millions of biomedical abstracts labelled with Medical Subject Headings. Free via NCBI.
- **arXiv paper classification:** Papers labelled by subject category. Free via Kaggle/arXiv bulk access.
- **Patent classification (CPC codes):** Google Patents Public Data on BigQuery. Millions of patents with hierarchical classification codes.

**What the project builds:**
- Fine-tune a small model (DistilBERT, DeBERTa-base, or a 7B LLM with QLoRA) on the labelled dataset
- Benchmark against zero-shot and few-shot prompting of large models (GPT-4, Claude) on the same test set
- Produce a cost-benefit analysis framework:
  - Accuracy curve: how does fine-tuned accuracy vary with training set size (10, 100, 1K, 10K, 100K examples)?
  - Cost curve: fine-tuning compute cost + inference cost vs. API cost per classification at different volumes
  - Latency comparison: ms per classification for local model vs. API call
  - Break-even analysis: "At N classifications/month, fine-tuning pays for itself"
- The deliverable isn't just "my model gets 94% accuracy" — it's a decision framework with specific crossover points

**PyTorch components used naturally:**
- HuggingFace Transformers (PyTorch backend) for model loading and fine-tuning
- Custom training loop or Trainer class with proper evaluation callbacks
- Learning rate scheduling, gradient accumulation for limited GPU memory
- QLoRA/LoRA adapters for efficient fine-tuning of larger models
- TorchMetrics or manual metric computation (precision, recall, F1 per class)
- Model export and inference benchmarking

**Pros:**
- Answers the most common production ML question: "build or buy?"
- The cost-benefit framework is the novel contribution, not the classification itself
- Multiple dataset options — can pick whichever domain best complements the portfolio
- CFPB complaints database ties to fintech (Revolut-relevant), PubMed ties to health (Clarity AI-relevant)
- Demonstrates practical engineering skills: GPU memory management, efficient fine-tuning, inference optimization
- The learning curve analysis (accuracy vs. training size) is genuinely useful and rarely shown in portfolios
- Strong interview talking points: when to fine-tune, LoRA mechanics, compute cost estimation, production deployment considerations

**Cons:**
- "Fine-tuning BERT for classification" is common — the framing must emphasise the cost-benefit analysis, not the fine-tuning itself
- Needs GPU access (Google Colab free tier, or a few dollars on cloud)
- Risk of appearing as a benchmark exercise rather than a business project if not framed well
- The "business impact" is indirect — it's a decision framework, not "this saves company X €Y"

**Novelty check needed:** Are there portfolio projects that frame fine-tuning as a cost-benefit decision framework rather than just "I fine-tuned a model"?

**Estimated scope:** 3-4 weeks

---

### Idea P2: Custom Embedding Model for Vertical Search

**Business question:** "In domain X, can a fine-tuned embedding model materially improve search/retrieval quality over general-purpose embeddings, and is the improvement worth the training cost?"

**Who pays for this today:** Any company with a domain-specific search problem — legal search (Casetext, now owned by Thomson Reuters), scientific literature search (Semantic Scholar), e-commerce product search (Algolia, Coveo), medical information retrieval.

**Data source candidates:**
- **Legal:** Case law from CourtListener (free, millions of US court opinions) or HUDOC (European Court of Human Rights)
- **Scientific:** BEIR benchmark datasets (standard IR evaluation), or S2ORC (Semantic Scholar Open Research Corpus)
- **E-commerce product matching:** Amazon ESCI dataset (exact product search relevance judgments, released for KDD Cup 2022)
- **Wine/food descriptions:** Could connect to the Private Label project if using food product descriptions from Open Food Facts

**What the project builds:**
- Start with an off-the-shelf sentence-transformer (e.g., `all-MiniLM-L6-v2`) as baseline
- Fine-tune on domain-specific similarity/relevance pairs using contrastive learning (MultipleNegativesRankingLoss or similar)
- Evaluate with standard IR metrics: NDCG@10, MRR, Recall@K on held-out queries
- Compare against: BM25 (sparse baseline), off-the-shelf embeddings (dense baseline), and hybrid (sparse + dense)
- Analysis: which query types improve most? Where does fine-tuning help vs. where BM25 was already good enough?
- If using the Amazon ESCI dataset: build a product search system that understands "running shoes for wide feet" means something different from "wide running shoe rack"

**PyTorch components used naturally:**
- SentenceTransformers library (PyTorch-based) for fine-tuning
- Custom contrastive loss functions
- Hard negative mining strategies
- Evaluation loops with IR metrics
- Embedding space visualisation (t-SNE/UMAP of before vs. after fine-tuning)
- Potentially ONNX export for inference benchmarking

**Pros:**
- Embeddings are the foundation of modern search AND RAG — directly relevant to LLM-era skills
- Standard evaluation metrics (NDCG, MRR) make the improvement quantifiable and credible
- The before/after comparison is visually compelling (embedding space plots, retrieval examples)
- Connects to recommendation systems experience (embeddings for item similarity)
- Amazon ESCI dataset is high-quality with human relevance judgments — perfect for rigorous evaluation
- Strong interview talking points: contrastive learning, hard negative mining, embedding space geometry, when dense beats sparse retrieval

**Cons:**
- "Fine-tuning sentence-transformers" is becoming more common as a tutorial topic
- The business impact framing is less direct than the other projects — "NDCG improved by 0.08" doesn't resonate with non-technical reviewers as strongly as "€X opportunity identified"
- Needs careful domain selection to avoid overlap with existing benchmarks that have already been optimised
- Evaluation requires constructing or finding query-relevance pairs, which can be labour-intensive

**Novelty check needed:** The Amazon ESCI product search angle may be well-trodden since it was a KDD Cup. Need to check. The legal/regulatory angle might be more novel and would tie to L1.

**Estimated scope:** 3-5 weeks

---

## Comparison Matrix

| Dimension | L1: Regulatory Intelligence | L2: Earnings Call Extractor | P1: Fine-Tune vs. Prompt | P2: Custom Embeddings |
|-----------|---------------------------|---------------------------|------------------------|---------------------|
| Framework | LangChain + vector store | LangChain + extraction chains | PyTorch + HuggingFace | PyTorch + SentenceTransformers |
| Business clarity | High — compliance is expensive | High — analyst time is expensive | Medium — it's a decision framework | Medium — search quality improvement |
| Data availability | Excellent (EUR-Lex is open) | Good (multiple free transcript sources) | Excellent (several labelled datasets) | Good (BEIR, ESCI, or domain-specific) |
| Evaluation rigour | Medium — need to construct ground truth | High — numbers are verifiable | High — standard classification metrics + cost analysis | High — standard IR metrics |
| Novelty risk | Low — regulatory RAG is niche | Medium — financial NLP is popular | Medium — fine-tuning is common, but cost framing may be novel | Medium — depends on domain choice |
| Portfolio fit | Strong — EU focus, connects to PL project | Strong — financial domain, Revolut-relevant | Strong — practical ML engineering | Good — connects to rec-sys background |
| Interview depth | Regulatory knowledge, RAG architecture, chunking strategy, evaluation | Financial domain, structured extraction, cross-document analysis | Fine-tuning mechanics, LoRA, cost estimation, production trade-offs | Contrastive learning, embedding geometry, retrieval evaluation |
| Scope | 4-5 weeks | 4-5 weeks | 3-4 weeks | 3-5 weeks |

## Next Steps

For each idea:
1. **Novelty verification** — search for existing portfolio projects with the same framing
2. **Data access confirmation** — actually try downloading/accessing the data
3. **Scope test** — can a minimal viable version be built in 1 week to validate feasibility?
4. **Business impact quantification** — can we fill in: "If implemented at a company with [parameters], this would [outcome worth $X]"?

We should pick **one LangChain project and one PyTorch project** to complement the two classical projects, giving a portfolio of four that spans: classical ML, data engineering, LLM/RAG systems, and deep learning fine-tuning.
