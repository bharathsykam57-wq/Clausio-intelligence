# LexIA v2 — Technical Write-up

> Fill this in as you build. The before/after RAGAS numbers are the most important part.
> Hiring managers read this to understand HOW you think, not just WHAT you built.

---

## Problem Statement

Legal professionals in France spend hours manually searching EU AI Act (144 pages) and GDPR (88 pages) for specific compliance answers. Keyword search misses semantic context. Generic LLMs hallucinate regulatory content they weren't trained on.

LexIA solves this with a RAG pipeline that grounds every answer in the source documents and measures retrieval quality with RAGAS.

---

## Why RAG Over Fine-tuning

| Approach | Pros | Cons |
|---|---|---|
| RAG | Auditable, updatable, cheap, citable | Retrieval quality-dependent |
| Fine-tuning | Fast inference | Expensive, static, hallucination-prone |

**Decision:** RAG because regulations update frequently, and because legal answers require citations — RAG makes source attribution trivial.

---

## Chunking Strategy

**Choice: RecursiveCharacterTextSplitter, 512 tokens, 64 overlap**

Tested 256, 512, and 1024:
- 256: Too granular — single sentences lose legal context
- **512: One full legal article — preserves argumentative structure**
- 1024: Too broad — dilutes retrieval with surrounding text

64-token overlap (12%) prevents answers cut at chunk boundaries without doubling storage.

---

## Embedding Model

**Choice: `mistral-embed` (1024 dimensions)**

- Native French support — critical for RGPD documents
- EU data residency — required for French enterprise clients
- Coherent stack with `mistral-large-latest` for generation

---

## Feature 1: Two-Stage Retrieval

**Problem:** Vector similarity is fast but imprecise — it matches style, not necessarily meaning.

**Solution:** Stage 1 fetches top-6 candidates from pgvector. Stage 2 cross-encoder reranks to top-3.

**Cross-encoder advantage:** Sees query + document together (bi-encoder sees them separately). Much more nuanced relevance scoring.

**Result:**
- context_precision baseline: `TODO`
- context_precision +reranker: `TODO`
- Improvement: `TODO`

**Trade-off:** +200ms latency. Acceptable for legal research where quality > speed.

---

## Feature 2: HyDE Retrieval

**Problem:** Multi-hop questions like "Compare GDPR consent with AI Act transparency" use question vocabulary that doesn't match document vocabulary.

**Solution:** Generate a hypothetical answer (~100 words in legal style), embed the hypothesis (not the query), search for similar document passages, then rerank against the original query.

**Key implementation detail:** Rerank against ORIGINAL query, not the hypothesis. Reranking against hypothesis tests "does this match my made-up answer" instead of "does this answer the user's question."

**Result:**
- context_recall before HyDE: `TODO`
- context_recall after HyDE: `TODO`
- Improvement: `TODO`

**Trade-off:** +1 LLM call per multi-hop query (~150ms). Only triggered for MULTI_HOP queries, not all queries.

---

## Feature 3: Query Router

**Problem:** Without classification, multi-hop questions get single-chunk retrieval (too little context) and out-of-scope questions cause hallucination.

**Solution:** Classify each query as SINGLE_CHUNK, MULTI_HOP, or OUT_OF_SCOPE. Route accordingly.

- SINGLE_CHUNK → standard retrieval, top_k=3
- MULTI_HOP → HyDE + top_k=6
- OUT_OF_SCOPE → skip retrieval, return "not in knowledge base"

**Uses `mistral-small-latest`** for classification — cheaper and faster than the large model. Classification doesn't require reasoning ability, just pattern matching.

**Result:**
- OOS hallucination rate before: `TODO`
- OOS hallucination rate after: `TODO`

---

## Feature 4: Contradiction Detection

**Problem:** EU AI Act and GDPR overlap on data processing. Retrieved chunks from both documents sometimes give different answers. Without detection, the LLM silently picks one.

**Solution:** When top chunk scores are within 0.15 of each other AND chunks come from different documents, check for contradictions with a short LLM prompt.

**Optimization:** Don't check for clear-cut cases (one dominant source). Only check when score proximity suggests multiple competing answers.

**Result:** Surface `TODO` genuine contradictions in test set.

---

## Feature 5: Confidence Scoring

**Problem:** Legal professionals need to know when to verify an answer independently.

**Solution:** Weighted average of rerank scores → HIGH/MEDIUM/LOW classification.

- HIGH (>0.80): Strong match, answer likely reliable
- MEDIUM (0.60–0.80): Partial match, verify with sources
- LOW (<0.60): Weak match, consult original documents

**Follow-up gate:** Only generate follow-up suggestions for MEDIUM+ confidence. Low confidence = current answer unreliable, suggesting follow-ups misleads users.

---

## RAGAS Evaluation History

| Run | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---|---|---|---|
| baseline | `TODO` | `TODO` | `TODO` | `TODO` |
| +reranker | `TODO` | `TODO` | `TODO` | `TODO` |
| +hyde | `TODO` | `TODO` | `TODO` | `TODO` |
| +router | `TODO` | `TODO` | `TODO` | `TODO` |
| final | `TODO` | `TODO` | `TODO` | `TODO` |

---

## Hardest Question Analysis

*[Find your lowest-scoring RAGAS question. Debug why it fails. Document here.]*

**Question:** `TODO`

**Why it fails:** `TODO`

**What I tried:** `TODO`

**Result:** `TODO`

---

## Known Limitations

1. **Multi-column PDFs:** PyPDF reads columns left-to-right, merging them incorrectly. Some regulatory annexes lose structure. Fix: `pdfplumber` with column detection.

2. **Table extraction:** Regulatory tables (e.g. risk categories in AI Act Annex III) lose their structure as flat text. Fix: table-aware chunking with `pdfplumber`.

3. **Scale ceiling:** IVFFlat index degrades past ~500k vectors. Production-scale would require HNSW index or migration to dedicated vector DB.

4. **Context window for very long multi-hop answers:** Some questions require 6+ passages that approach the 4k context limit. Fix: map-reduce summarization for very long contexts.

---

## Future Improvements

- [ ] HNSW index for better scaling beyond 500k vectors
- [ ] Parent-document retriever: retrieve small chunks, return their larger parent
- [ ] Query rewriting with LLM for ambiguous questions
- [ ] User feedback collection for reranker fine-tuning
- [ ] Streaming contradiction detection (run in parallel with generation)
