# Clausio — Technical Write-up

> Last updated: March 5, 2026 — Week 1 Complete
> Hiring managers read this to understand HOW you think, not just WHAT you built.

---

## Problem Statement

Legal professionals and compliance officers working with EU AI regulation spend hours manually searching two dense documents: the EU AI Act (Regulation EU 2024/1689, 144 pages) and the GDPR/RGPD (88 pages). Keyword search misses semantic context — searching "AI system definition" will not find the passage that says "machine-based system designed to operate with varying levels of autonomy." Generic LLMs hallucinate regulatory content they were not trained on, or confidently cite articles that do not exist.

Clausio solves this with a RAG pipeline that grounds every answer in the source documents, attributes every claim to a specific chunk, and measures retrieval quality automatically with RAGAS so improvements can be quantified rather than estimated.

---

## Why RAG Over Fine-tuning

| Approach | Pros | Cons |
|---|---|---|
| RAG | Auditable, updatable, cheap, citable | Retrieval quality-dependent |
| Fine-tuning | Fast inference | Expensive, static, hallucination-prone, hard to update |

**Decision:** RAG because EU regulations update frequently — the EU AI Act went through multiple amendments before final adoption. With RAG, updating the knowledge base means re-ingesting a new PDF. With fine-tuning, it means retraining the model. RAG also makes source attribution trivial: every answer traces to specific chunks with page numbers. For a legal compliance tool, "here is the article this comes from" is not optional.

---

## System Architecture

The pipeline has three independent phases. Each is replaceable without touching the others.

### Phase 1 — Ingestion (one-time)

```
PDF files → PyPDF (text extraction) → LangChain RecursiveCharacterTextSplitter
→ Mistral embed API (1024 dimensions) → pgvector PostgreSQL (Docker)
```

**Documents ingested:**
- EU AI Act: 2.5MB PDF, yielded 398 chunks
- RGPD (French): 1.0MB PDF, yielded 252 chunks
- **Total corpus: 650 chunks**

### Phase 2 — Retrieval (per query)

```
User question → Query Router (mistral-small) → [SINGLE_CHUNK | MULTI_HOP | OUT_OF_SCOPE]
    SINGLE_CHUNK → pgvector cosine search → cross-encoder rerank → top 3 chunks
    MULTI_HOP    → HyDE hypothesis → pgvector search → cross-encoder rerank → top 6 chunks
    OUT_OF_SCOPE → return refusal message (zero retrieval cost)
```

### Phase 3 — Generation (per query)

```
Top chunks + question → mistral-large-latest → cited answer
→ confidence scoring → follow-up suggestions → Redis cache (1hr TTL)
```

---

## Chunking Strategy

**Choice: RecursiveCharacterTextSplitter, chunk_size=2048, chunk_overlap=256**

The splitter tries splitting points in this order: paragraph breaks (`\n\n`), then line breaks (`\n`), then sentences (`.`), then characters. This preserves legal article structure — a legal article rarely spans multiple paragraphs, so paragraph-level splitting usually produces one article per chunk.

- **chunk_overlap=256** (12.5%): prevents answers being cut at chunk boundaries. A question about Article 13 will still find the answer even if the chunk starts 200 tokens into Article 13.
- **Why not 512 tokens:** At 512 tokens, single sentences lose legal cross-references. The EU AI Act frequently references other articles within the same article. Keeping 2048 tokens preserves these intra-article references.

---

## Embedding Model

**Choice: `mistral-embed` (1024 dimensions)**

- Native French support — critical for RGPD documents
- EU data residency — data never leaves European infrastructure
- Coherent stack with `mistral-large-latest` for generation (same tokenizer, aligned semantic spaces)
- **Cost: ~$0.00005 per chunk** — total ingestion cost for 650 chunks: approximately $0.033

---

## Infrastructure Decisions

### pgvector over Pinecone/Qdrant

Three reasons:
1. **Data sovereignty**: For EU regulatory compliance, keeping vectors in your own PostgreSQL means data never leaves your infrastructure. GDPR compliant by design.
2. **One less service**: pgvector is a PostgreSQL extension — no separate vector database to manage, monitor, or pay for. One Docker container handles both relational data and vector search.
3. **SQL joins**: Vector search results can be joined with relational data (users, request logs, rate limit tables) in the same query. Dedicated vector databases cannot do this.

**IVFFlat index configuration:**
- `lists=10` for current corpus size (650 chunks)
- Rule: `lists = corpus_size / 39`. At 650 chunks, lists=10 is optimal.
- When corpus grows beyond 3,900 chunks, upgrade to `lists=100`
- Index created separately from table initialization — `create_ivfflat_index()` called after ingestion, not at startup

### Docker for local development

Both PostgreSQL (with pgvector) and Redis run in Docker containers via `docker-compose up -d db redis`. This eliminates "works on my machine" problems and matches the production Railway deployment exactly.

---

## Feature 1: Query Router

**Problem:** Without classification, all questions get the same retrieval strategy. Multi-hop questions get insufficient context. Out-of-scope questions cause hallucination.

**Solution:** Classify each query as SINGLE_CHUNK, MULTI_HOP, or OUT_OF_SCOPE using mistral-small-latest before retrieval.

- `SINGLE_CHUNK` → standard cosine search, top_k=3, standard retrieval
- `MULTI_HOP` → HyDE retrieval, top_k=6, broader context
- `OUT_OF_SCOPE` → return refusal immediately, zero vector search, zero generation cost

**Uses `mistral-small-latest` not `mistral-large`:** Classification is a pattern-matching task, not a reasoning task. mistral-small costs 5x less per call and adds only 50ms. The savings accumulate significantly at scale.

**Verified result:**
- SINGLE_CHUNK: "What is the definition of an AI system?" → correctly classified, cited Article 3(1)
- MULTI_HOP: "How do GDPR data rights interact with EU AI Act?" → correctly activated HyDE
- OUT_OF_SCOPE: "What is the current interest rate in France?" → clean refusal, zero API cost

---

## Feature 2: HyDE Retrieval

**Problem:** Multi-hop questions use question vocabulary that does not match document vocabulary. "Compare GDPR consent with AI Act transparency" uses no words that appear in the relevant regulation articles.

**Solution:** HyDE (Hypothetical Document Embeddings) generates a fake regulation article (~100 words in legal style) that answers the question. The hypothesis is embedded and used for vector search. The retrieved chunks are then reranked against the **original query** (not the hypothesis).

**Why rerank against the original query:** Reranking against the hypothesis would test "does this chunk match my made-up answer" instead of "does this chunk answer the user's question." The hypothesis is a search tool, not the target.

**Observed behaviour:** For the MULTI_HOP test query, HyDE generated:
> "Article 12 – Interaction of Data Rights and AI System Obligations. Where the processing of personal data..."

This fake article does not exist in either regulation, but because it uses correct legal vocabulary and article structure, it retrieved highly relevant chunks with scores above 0.80.

**Trade-off:** +1 mistral-small call per multi-hop query (~150ms, ~$0.0001). Only triggered for MULTI_HOP classification.

---

## Feature 3: Two-Stage Retrieval with Cross-Encoder Reranking

**Problem:** Vector similarity (bi-encoder) is fast but imprecise. It encodes query and document independently, then compares vectors. It matches style and topic but misses fine-grained relevance.

**Solution:** Stage 1 fetches top-6 candidates from pgvector (fast, approximate). Stage 2 passes each candidate to a cross-encoder that reads the query and document together and scores their relevance jointly.

**Cross-encoder model:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (471MB, downloaded once to `~/.cache/huggingface/`)

**Cross-encoder advantage:** Reads query + document simultaneously — can detect when a document uses different words to express the same concept, or when a document uses the same words in a different context.

**Trade-off:** +200ms latency for the reranking step. Acceptable for legal research where precision matters more than speed.

**RAGAS result:** context_precision baseline = 0.500. Target after reranker tuning: >0.700.

---

## Feature 4: Confidence Scoring

**Problem:** Legal professionals need to know when an answer is reliable enough to act on and when to verify independently.

**Solution:** Weighted average of cross-encoder rerank scores produces a single confidence score, classified as HIGH/MEDIUM/LOW.

- `HIGH` (>0.80): Strong match — answer likely reliable
- `MEDIUM` (0.60–0.80): Partial match — verify with source documents
- `LOW` (<0.60): Weak match — consult original documents directly

**Follow-up gate:** Follow-up question suggestions are only generated for MEDIUM+ confidence. Generating follow-ups for a LOW confidence answer would imply the current answer is reliable enough to build on — it is not.

**Observed in testing:** Definition questions like "What is an AI system?" score MEDIUM, not HIGH. This is correct — the EU AI Act definition appears across multiple chunks (Article 3, recitals, annexes) with similar relevance scores. The system correctly reports uncertainty when multiple passages are equally relevant rather than falsely claiming high confidence.

---

## Feature 5: Redis Caching and Rate Limiting

**Response caching:** Answers are cached in Redis with a 1-hour TTL using a hash of the question as the key. Second request for an identical question: 5ms response time, zero API cost. First request: ~2 seconds, ~$0.002.

**Rate limiting:** Sliding window counter per user stored in Redis sorted sets.
- 20 requests per minute
- 200 requests per day
- Returns HTTP 429 with retry-after header when exceeded
- Graceful degradation: if Redis is unavailable, rate limiting is skipped (system continues working)

---

## Feature 6: Contradiction Detection

**Problem:** EU AI Act and GDPR overlap on data processing obligations. Retrieved chunks from both documents sometimes give different answers on the same topic. Without detection, the LLM silently picks one.

**Solution:** When top chunk scores are within 0.15 of each other AND chunks come from different source documents, run a short contradiction-check prompt. Only triggers when score proximity genuinely suggests competing answers — avoids unnecessary LLM calls for clear-cut cases.

---

## RAGAS Evaluation Results

**Configuration:**
- Judge LLM: `mistral-small-latest` (cost-efficient, sufficient for scoring tasks)
- Embeddings: `mistral-embed`
- Test set: 5 questions (subset, excluding OUT_OF_SCOPE)
- `raise_exceptions=False` to handle async timeouts gracefully

| Run | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---|---|---|---|
| baseline | **0.917** | n/a (timeout) | **0.500** | **0.838** |
| +reranker_tuned | — | — | — | — |
| +hyde_improved | — | — | — | — |
| +multilingual | — | — | — | — |
| final | — | — | — | — |

### Baseline Score Analysis

**faithfulness: 0.917** — The model stays grounded in retrieved text 91.7% of the time. The 8.3% gap represents minor elaborations where the model adds context not directly quoted from a chunk. For a legal compliance tool this should be pushed toward 1.0 in production. Strong starting point.

**answer_relevancy: n/a** — Timed out during async evaluation, not a quality issue. RAGAS fires all metric scoring calls concurrently via asyncio. Answer relevancy is the most expensive metric (generates multiple paraphrased questions per answer). Under Mistral API rate limits, these calls timed out. Fixed by `raise_exceptions=False`. Will be re-measured in isolation.

**context_precision: 0.500** — Primary improvement target. Half of the retrieved chunks are not useful for answering the question. The cross-encoder reranker retrieves 6 candidates and passes all 6 to generation. The fix: set a minimum rerank score threshold (~0.3) and drop chunks that fall below it. Expect this to rise above 0.700 after tuning.

**context_recall: 0.838** — The system finds 83.8% of the passages needed to answer correctly. The 16.2% gap is mostly in multi-hop queries where vocabulary mismatch prevents finding relevant chunks. HyDE should push this above 0.880.

---

## Known Limitations

### 1. Multilingual Retrieval Gap
English queries do not retrieve French RGPD chunks effectively. The cross-encoder reranker underweights French text when scoring against an English query. Tested directly: asking "How do GDPR data rights interact with EU AI Act obligations?" returned all 6 sources from the English EU AI Act — zero from the French RGPD.

**Planned fix (Week 2):** Language detection on incoming query → if RGPD-specific, translate query to French → run parallel retrieval (English query vs EU AI Act, French query vs RGPD) → merge and rerank combined results.

### 2. PDF Two-Column Layout Artifacts
PyPDF reads the Official Journal two-column layout by scanning character positions left-to-right across both columns simultaneously. This produces minor spacing artifacts: "syste m" instead of "system", "marke t" instead of "market". Retrieval scores remain above 0.80 because transformer embedding models are robust to this noise. Main impact is answer text readability.

**Engineering decision:** Three regex cleaning attempts produced worse artifacts (merging word boundaries incorrectly). Each attempt required a full re-ingestion at ~$0.08. After measuring that retrieval quality was not affected, accepted the limitation rather than spending more API budget on a cosmetic fix.

**Planned fix:** Replace PyPDF with `pdfplumber` which has layout-aware column extraction. Document this as a future improvement rather than blocking current work.

### 3. IVFFlat Index Minimum Row Requirement
IVFFlat index requires `lists × 39` minimum rows to build cluster assignments. With `lists=100` that is 3,900 rows minimum. Current corpus is 650 chunks. Index runs with `lists=10` to accommodate current corpus size. Will upgrade to `lists=100` when corpus grows to 3,900+ chunks.

### 4. External URL Dependency
Original ingestion script used hardcoded EUR-Lex and CNIL PDF URLs. Both links broke within months — EUR-Lex restructured their URL scheme, CNIL moved their file. Switched to local file ingestion with `--pdf` flag.

**Production fix:** Download PDFs to object storage (S3/R2) on first run. Point ingestion at own storage. External URLs rot. Own storage does not.

### 5. answer_relevancy Scoring Timeout
RAGAS async runner times out under Mistral API rate limits for the answer_relevancy metric. `raise_exceptions=False` prevents crashes but leaves the metric as `nan`. To be measured with extended timeout configuration.

---

## Debugging Log Summary

All significant bugs encountered and resolved are documented in:
- `docs/DEBUG_LOG.md` — pgvector + SQLAlchemy issues (Days 1–4)
- `docs/DEBUG_LOG_VOL2.md` — PDF ingestion URL failures and regex decisions (Day 5)
- `docs/DEBUG_LOG_VOL3.md` — RAGAS OpenAI conflict and async timeout fixes (Day 6)

**Most significant bug:** IVFFlat index silently returning 0 results for all similarity searches. Root cause: index requires 3,900 minimum rows; test data had 13. Discovered by dropping the index and observing immediate correct results. Fix: separate index creation from table initialization. Full analysis in DEBUG_LOG.md.

---

## Week 2 Targets

- [ ] Tune cross-encoder threshold to push context_precision above 0.700
- [ ] Parallel multilingual retrieval for RGPD queries
- [ ] Measure answer_relevancy with extended timeout
- [ ] Re-run RAGAS after each improvement and update table above
- [ ] Replace PyPDF with pdfplumber for cleaner text extraction
- [ ] Deploy to Railway and test with real user queries

---

## Future Improvements

- HNSW index for better scaling beyond 500k vectors (currently IVFFlat)
- Parent-document retriever: retrieve small chunks, return their larger parent for context
- Query rewriting for ambiguous questions before retrieval
- User feedback collection for reranker fine-tuning
- Streaming contradiction detection (run in parallel with generation, not sequentially)
- Multi-tenant vector stores for SaaS deployment (isolated namespaces per client)
