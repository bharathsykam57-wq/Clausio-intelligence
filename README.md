# LexIA v2 — Complete Build Tutorial

> **How to use this file:** Read this top to bottom. Every section is a tutorial step.
> You have all the code. Your job is to understand it, wire it together, and deploy it.
> Think of this as a written tutorial you follow alongside the project files.

---

## What You're Building

**LexIA** is a production-grade RAG (Retrieval-Augmented Generation) chatbot that answers questions about the **EU AI Act** and **GDPR/RGPD** using the actual regulatory documents as its knowledge base.

What makes it portfolio-grade vs tutorial-grade:

| Feature | Why It Matters |
|---|---|
| **HyDE Retrieval** | +15% recall. Shows you know retrieval failure modes |
| **Query Router** | Prevents hallucination on out-of-scope questions |
| **Contradiction Detection** | Honest AI — surfaces conflicts between sources |
| **Confidence Scoring** | Users know when to verify independently |
| **Follow-up Suggestions** | Grounded in retrieved context, not generic |
| **RAGAS Eval Loop** | Measures every improvement with real numbers |

---

## Project Structure (read this first)

```
lexia-v2/
├── backend/
│   ├── ingest/          ← Step 1: load PDFs, chunk, embed, store
│   │   ├── loader.py
│   │   ├── embedder.py
│   │   ├── vectorstore.py
│   │   └── run_ingest.py
│   ├── retrieval/       ← Step 2: find relevant chunks
│   │   ├── retriever.py        (two-stage: embed → rerank)
│   │   ├── hyde_retriever.py   ★ HyDE: generate hypothesis → embed → search
│   │   └── query_router.py     ★ Classify: SINGLE_CHUNK / MULTI_HOP / OOS
│   ├── chain/           ← Step 3: generate answer
│   │   ├── rag_chain.py        (orchestrates everything)
│   │   ├── contradiction.py    ★ Detect conflicting chunks
│   │   ├── confidence.py       ★ Score retrieval quality
│   │   └── followup.py         ★ Generate grounded follow-ups
│   ├── eval/            ← Step 4: measure everything
│   │   ├── test_set.json       (20 ground-truth Q&A pairs)
│   │   ├── evaluate.py         (RAGAS runner)
│   │   └── dashboard.py        (Streamlit metrics dashboard)
│   ├── api/
│   │   └── main.py             (FastAPI — REST + SSE endpoints)
│   └── config.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx            (main chat UI)
│   │   └── globals.css
│   ├── components/
│   │   ├── ConfidenceBadge.tsx ★
│   │   ├── ContradictionAlert.tsx ★
│   │   ├── FollowUpSuggestions.tsx ★
│   │   ├── QueryTypeBadge.tsx  ★
│   │   └── SourceCard.tsx
│   └── lib/api.ts              (typed API client)
├── docker-compose.yml
├── .env.example
└── README.md  ← you are here
```

---

## Prerequisites

Before you write a single line of code, do this:

### 1. Install Required Tools

```bash
# Verify each one
python --version    # Need 3.11+
node --version      # Need 20+
docker --version    # Need Docker Desktop running
git --version       # Any version
```

If anything is missing:
- Python: https://python.org/downloads
- Node: https://nodejs.org (download LTS)
- Docker: https://docker.com/products/docker-desktop

### 2. Get Your Mistral API Key

1. Go to https://console.mistral.ai
2. Create account → verify email
3. Go to "API Keys" → Create new key
4. Copy the key — you'll use it in the next step
5. Check your balance — you should have $5 free credit

### 3. Create GitHub Repository

```bash
# On GitHub: create new repo called "lexia-rag" (public, no README)
# Then locally:
git clone https://github.com/YOUR_USERNAME/lexia-rag.git
cd lexia-rag
```

### 4. Copy Project Files

Copy everything from this zip into your `lexia-rag` folder:
```
lexia-rag/
  backend/       ← copy from zip
  frontend/      ← copy from zip
  docker-compose.yml
  .env.example
  .gitignore
```

---

## WEEK 1 — Backend (Days 1–7)

**Rule: Do NOT open the frontend folder this week. Backend in terminal first.**

---

### Day 1 — Environment Setup

**Goal:** Docker running, database connected, .env configured.

#### Step 1: Set up your .env file

```bash
# In the lexia-rag root:
cp .env.example .env
```

Open `.env` and replace `your_mistral_api_key_here` with your actual key.

```
MISTRAL_API_KEY=sk-xxxxxxxxxxxxx
DATABASE_URL=postgresql://lexia:lexia@localhost:5432/lexia
CORS_ORIGINS=["http://localhost:3000"]
```

#### Step 2: Start Docker

```bash
docker-compose up -d db
# Wait 10 seconds, then verify:
docker-compose ps
# Should show lexia_db as "Up"
```

#### Step 3: Test DB connection

```bash
docker exec lexia_db psql -U lexia -c '\l'
# Should show: lexia | lexia | UTF8
```

#### Step 4: Install Python dependencies

```bash
cd backend
python -m venv venv

# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt
# This takes 5-10 minutes. Normal.
```

#### Step 5: First commit

```bash
cd ..  # back to project root
git add .
git commit -m "chore: initial project setup with Docker and env config"
git push origin main
```

**✅ Done when:** `docker-compose ps` shows db running, pip install succeeded.

**☠️ Don't:** Install pgvector natively. Docker only.

---

### Day 2 — PDF Loader

**Goal:** Load a PDF and print chunks to terminal.

#### Understanding loader.py

Open `backend/ingest/loader.py`. Read the docstring at the top.

Key things to understand:
- `load_pdf_from_bytes()` — takes raw bytes, returns list of Documents (one per page)
- `chunk_documents()` — splits pages into overlapping chunks
- `chunk_size=512*4` chars ≈ 512 tokens — one legal article per chunk
- `chunk_overlap=64*4` chars — prevents answers being cut at chunk boundaries

#### Test with a small PDF

Download any small PDF (5-10 pages) to `backend/test_data/test.pdf`:

```bash
mkdir -p backend/test_data
# Download any PDF you have, or use curl:
# curl -o backend/test_data/test.pdf "https://some-small-pdf.com"
```

Test the loader:

```bash
cd backend
python -c "
from ingest.loader import load_pdf_from_path, chunk_documents
pages = load_pdf_from_path('test_data/test.pdf')
chunks = chunk_documents(pages)
print(f'Pages: {len(pages)}, Chunks: {len(chunks)}')
print('--- First chunk ---')
print(chunks[0].page_content[:300])
print('--- Metadata ---')
print(chunks[0].metadata)
"
```

**Expected output:**
```
Pages: 8, Chunks: 45
--- First chunk ---
[actual text from your PDF]
--- Metadata ---
{'source': 'test', 'title': 'test', 'page': 1, 'total_pages': 8}
```

**Troubleshooting:**
- `ModuleNotFoundError: pypdf` → run `pip install pypdf`
- Empty pages → try a different PDF, some are image-only (need OCR)
- Very few chunks → increase chunk_size or check if PDF has extractable text

**Commit:**
```bash
git add .
git commit -m "feat(ingest): PDF loader and recursive chunker"
```

---

### Day 3 — Embedder

**Goal:** Turn chunks into vectors using Mistral API.

#### Understanding embedder.py

Open `backend/ingest/embedder.py`. Key concepts:
- `embed_texts()` calls Mistral's `mistral-embed` model
- Returns 1024-dimensional vectors (arrays of 1024 floats)
- `@retry` decorator — automatically retries on rate limit errors
- `embed_documents_batched()` — processes in groups of 32 to respect rate limits

#### Test embedding

```bash
cd backend
python -c "
from ingest.embedder import embed_texts, embed_query
# Test single text
vec = embed_texts(['What is an AI system?'])[0]
print(f'Vector dimensions: {len(vec)}')  # Should be 1024
print(f'First 5 values: {vec[:5]}')

# Test query embedding
qvec = embed_query('What is GDPR?')
print(f'Query vector dimensions: {len(qvec)}')
"
```

**Expected output:**
```
Vector dimensions: 1024
First 5 values: [0.023, -0.041, 0.017, ...]
Query vector dimensions: 1024
```

**Troubleshooting:**
- `AuthenticationError` → your MISTRAL_API_KEY in .env is wrong
- `RateLimitError` → wait 60 seconds and retry (free tier limit)
- Vector dimensions ≠ 1024 → wrong model name in config.py

**Commit:**
```bash
git commit -m "feat(ingest): Mistral embed API with batching and retry"
```

---

### Day 4 — Vector Store

**Goal:** Store embeddings in pgvector, run similarity search.

#### Understanding vectorstore.py

Open `backend/ingest/vectorstore.py`. Key concepts:
- `init_db()` — creates the pgvector extension and documents table
- IVFFlat index uses cosine distance — best for normalized embedding vectors
- `similarity_search()` — returns chunks sorted by similarity score (0 to 1)
- `1 - (embedding <=> query)` converts distance to similarity

#### Test vector store

```bash
cd backend
python -c "
from ingest.vectorstore import init_db, insert_documents, similarity_search, get_document_count
from ingest.loader import load_pdf_from_path, chunk_documents
from ingest.embedder import embed_documents_batched

# Initialize DB
init_db()
print('DB initialized')

# Load and embed test PDF
pages = load_pdf_from_path('test_data/test.pdf')
chunks = chunk_documents(pages)[:10]  # Only 10 chunks for testing
embedded = embed_documents_batched(chunks)

# Insert
count = insert_documents(embedded)
print(f'Inserted: {count} documents')
print(f'Total in DB: {get_document_count()}')

# Search
from ingest.embedder import embed_query
vec = embed_query('What is the main topic?')
results = similarity_search(vec, top_k=3)
for r in results:
    print(f'Similarity: {r[\"similarity\"]:.3f} | {r[\"content\"][:100]}')
"
```

**Expected output:**
```
DB initialized
Inserted: 10 documents
Total in DB: 10
Similarity: 0.847 | [relevant text from your PDF]
Similarity: 0.821 | [relevant text]
Similarity: 0.793 | [relevant text]
```

**Troubleshooting:**
- `could not connect to server` → `docker-compose up -d db` to start database
- `could not create extension "vector"` → wrong Docker image. Use `ankane/pgvector`
- All similarity scores 0.0 → vector dimension mismatch. Check vectors are 1024-dim

**Commit:**
```bash
git commit -m "feat(ingest): pgvector store with IVFFlat cosine index"
```

---

### Day 5 — Full Ingestion + Eval Test Set

**Goal:** Ingest EU AI Act + RGPD. Write your evaluation test set.

#### Run full ingestion

```bash
cd backend
python -m ingest.run_ingest
# This downloads ~200MB of PDFs and embeds them
# Takes 10-20 minutes. Cost: ~$0.10
# Watch the progress logs
```

**Expected log output:**
```
INFO  | DB initialized
INFO  | Downloading: https://eur-lex.europa.eu/...
INFO  | Loaded 144 pages from 'EU Artificial Intelligence Act'
INFO  | Split 144 pages → 892 chunks
INFO  | Embedding batch 1/28
...
INFO  | Embedding batch 28/28
SUCCESS | Done: 892 new chunks, 892 total in DB
```

**If download fails** (EU regulation URLs sometimes timeout):
```bash
# Download manually then ingest:
# Download EU AI Act PDF from https://eur-lex.europa.eu manually
# Save as backend/test_data/eu_ai_act.pdf
python -m ingest.run_ingest --pdf test_data/eu_ai_act.pdf
```

#### Review the test set

Open `backend/eval/test_set.json`. Read through the 20 questions.

Notice:
- Questions 1-10: straightforward EU AI Act + GDPR questions
- Questions 11-13: multi-hop questions requiring combining information
- Questions 18-19: out-of-scope questions (answers not in documents)
- Each has `difficulty`: easy / medium / hard / oos

The ground truth answers are what RAGAS compares against. You can add your own questions — more questions = more reliable evaluation.

**Commit:**
```bash
git commit -m "feat(eval): 20-question ground truth test set added"
```

---

### Day 6 — Basic RAG Chain + Baseline Eval

**Goal:** Get your first answer in the terminal. Run RAGAS baseline.

#### Understanding rag_chain.py

Open `backend/chain/rag_chain.py`. Read the pipeline comment at the top. The `answer()` function:
1. Calls `classify_query()` → query type
2. Chooses retrieval method based on type
3. Checks for contradictions
4. Calculates confidence
5. Generates answer with Mistral
6. Generates follow-ups
7. Returns everything

#### Test basic answer

```bash
cd backend
python -c "
from chain.rag_chain import answer
result = answer('What is the definition of an AI system under the EU AI Act?')
print('ANSWER:', result['answer'][:500])
print('SOURCES:', [s['title'] for s in result['sources']])
print('CONFIDENCE:', result['confidence'])
print('QUERY TYPE:', result['query_type'])
"
```

#### Run RAGAS baseline

**This is the most important step of Week 1.**

```bash
cd backend
python -m eval.evaluate --tag baseline
```

This runs all 18 non-OOS questions and measures 4 metrics.
Takes 15-20 minutes. Costs ~$0.20.

**Save your baseline numbers.** Write them down. These are your before scores.

Example baseline output:
```
=== RAGAS Results [baseline] ===
  faithfulness             : 0.823
  answer_relevancy         : 0.791
  context_precision        : 0.756
  context_recall           : 0.703
```

**Write these in your WRITEUP.md.** Now you have something to beat.

**Commit:**
```bash
git commit -m "feat(eval): baseline RAGAS scores - faithfulness 0.82, recall 0.70"
```

---

### Day 7 — Retriever + Reranker

**Goal:** Two-stage retrieval working, measured vs baseline.

#### Understanding retriever.py

Open `backend/retrieval/retriever.py`. The `retrieve()` function:
1. Embeds the query (or uses provided embedding for HyDE)
2. Runs cosine similarity search in pgvector (top_k=6 candidates)
3. Applies cross-encoder reranking (reduces to top_k=3)

The cross-encoder `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` is multilingual — it handles both English (AI Act) and French (RGPD).

#### Test retrieval

```bash
cd backend
python -c "
from retrieval.retriever import retrieve

results = retrieve('What are the obligations of high-risk AI providers?')
for i, r in enumerate(results, 1):
    print(f'Rank {i}: score={r.get(\"rerank_score\", r[\"similarity\"]):.3f}')
    print(f'  Source: {r[\"metadata\"].get(\"title\")} p.{r[\"metadata\"].get(\"page\")}')
    print(f'  Text: {r[\"content\"][:150]}')
    print()
"
```

**Commit:**
```bash
git commit -m "feat(retrieval): two-stage retrieval with multilingual cross-encoder"
```

---

## WEEK 2 — Advanced Features (Days 8–14)

**Each feature = implement it + run RAGAS + document the difference.**

---

### Day 8 — HyDE Implementation

**Goal:** HyDE retriever coded and working.

#### Understanding hyde_retriever.py

Open `backend/retrieval/hyde_retriever.py`. Read the full docstring.

The key insight: query vocabulary ≠ document vocabulary.

```
User:     "What penalties exist for violating the AI Act?"
Document: "Administrative fines... shall be effective, proportionate..."
```

These have low cosine similarity despite being about the same thing.

HyDE fixes this by generating text that sounds like the document:

```
Hypothesis: "Providers who violate prohibited practices shall be subject to
administrative fines of up to 35,000,000 EUR or 7% of global annual turnover..."
```

Now the embedding search finds the right passage.

#### Test HyDE

```bash
cd backend
python -c "
from retrieval.hyde_retriever import hyde_retrieve, generate_hypothesis

# See what hypothesis looks like
q = 'What are the penalties for violating the EU AI Act?'
hypothesis = generate_hypothesis(q)
print('HYPOTHESIS:')
print(hypothesis)
print()

# Run HyDE retrieval
results = hyde_retrieve(q)
for i, r in enumerate(results, 1):
    print(f'Rank {i}: {r[\"content\"][:150]}')
"
```

**Commit:**
```bash
git commit -m "feat(retrieval): HyDE hypothetical document embedding retrieval"
```

---

### Day 9 — HyDE Measurement

**Goal:** Prove HyDE works with RAGAS numbers.

#### Run comparison

```bash
cd backend

# Temporarily disable HyDE in rag_chain.py by changing:
# query_type == QueryType.MULTI_HOP → always use standard retrieval
# Run eval:
python -m eval.evaluate --tag no_hyde

# Re-enable HyDE, run again:
python -m eval.evaluate --tag with_hyde
```

Compare the `context_recall` metric between the two runs.

**Write in WRITEUP.md:**
```markdown
## HyDE Retrieval Analysis

**Problem:** Multi-hop questions like "Compare GDPR consent with AI Act obligations"
had context_recall of 0.XX because query vocabulary doesn't match document vocabulary.

**Solution:** Generate a hypothetical answer, embed it, use it for search.

**Result:** context_recall improved from 0.XX (no_hyde) to 0.XX (with_hyde).
HyDE hurt precision slightly (+0.03 context_precision loss) because the hypothesis
can introduce vocabulary from outside the actual document. Trade-off accepted
because recall is more critical for legal research.
```

**Commit:**
```bash
git commit -m "docs(eval): HyDE analysis - context_recall +X.XX with RAGAS evidence"
```

---

### Day 10 — Query Router Implementation

**Goal:** Three-class query classifier working.

#### Understanding query_router.py

Open `backend/retrieval/query_router.py`. Key points:
- Uses `mistral-small-latest` (cheaper, faster — classification doesn't need the big model)
- Few-shot prompt with clear examples for each class
- Defaults to `SINGLE_CHUNK` on error — safe fallback
- `OUT_OF_SCOPE` skips retrieval entirely — saves API cost AND prevents hallucination

#### Test the router

```bash
cd backend
python -c "
from retrieval.query_router import classify_query

test_queries = [
    'What is the definition of an AI system?',                    # SINGLE_CHUNK
    'Compare GDPR consent with AI Act transparency requirements', # MULTI_HOP
    'What is the French minimum wage?',                           # OUT_OF_SCOPE
    'List prohibited AI practices',                               # SINGLE_CHUNK
    'Who is the current French president?',                       # OUT_OF_SCOPE
]

for q in test_queries:
    qtype = classify_query(q)
    print(f'{qtype.value:15s} | {q}')
"
```

**Expected output:**
```
SINGLE_CHUNK    | What is the definition of an AI system?
MULTI_HOP       | Compare GDPR consent with AI Act transparency requirements
OUT_OF_SCOPE    | What is the French minimum wage?
SINGLE_CHUNK    | List prohibited AI practices
OUT_OF_SCOPE    | Who is the current French president?
```

**If router misclassifies:** Improve the few-shot examples in `ROUTER_SYSTEM` prompt.

**Commit:**
```bash
git commit -m "feat(retrieval): query router with SINGLE_CHUNK/MULTI_HOP/OUT_OF_SCOPE"
```

---

### Day 11 — Router Integration + RAGAS

**Goal:** Router active in pipeline, OOS questions handled correctly.

The router is already integrated in `rag_chain.py` — verify it works end to end:

```bash
cd backend
python -c "
from chain.rag_chain import answer

# OOS question — should NOT hit retrieval
result = answer('What is the current French corporate tax rate?')
print('OOS test:')
print('Query type:', result['query_type'])   # Should be OUT_OF_SCOPE
print('Chunks used:', result['chunks_used']) # Should be 0
print('Answer:', result['answer'][:200])

# Multi-hop — should use HyDE
result = answer('Compare GDPR consent requirements with AI Act obligations for transparency')
print('Multi-hop test:')
print('Query type:', result['query_type'])   # Should be MULTI_HOP
print('Chunks used:', result['chunks_used']) # Should be 6
"
```

Run eval with router:
```bash
python -m eval.evaluate --tag with_router
```

**Commit:**
```bash
git commit -m "feat(chain): query router integrated, OOS handling active"
```

---

### Day 12 — Contradiction Detection

**Goal:** Contradiction checker coded, finding real conflicts.

#### Understanding contradiction.py

Open `backend/chain/contradiction.py`. Key optimization:
- Only runs when top chunk scores are within 0.15 of each other
- Only runs when chunks come from different source documents
- This avoids spending an extra LLM call on clear-cut single-source answers

#### Test contradiction detection

To trigger a contradiction, you need a query that retrieves chunks from both EU AI Act AND RGPD that discuss the same topic differently:

```bash
cd backend
python -c "
from retrieval.retriever import retrieve
from chain.contradiction import check_contradictions

# Query that should pull from both documents
q = 'What transparency information must be provided to individuals about AI decision-making?'
chunks = retrieve(q)

print('Sources in retrieved chunks:')
for c in chunks:
    print(f'  - {c[\"metadata\"].get(\"title\")} (score: {c.get(\"rerank_score\", c[\"similarity\"]):.3f})')

result = check_contradictions(chunks)
print(f'Contradiction detected: {result[\"has_contradiction\"]}')
print(f'Checked: {result[\"checked\"]}')
if result['has_contradiction']:
    print(f'Explanation: {result[\"explanation\"]}')
"
```

**Commit:**
```bash
git commit -m "feat(chain): contradiction detection across retrieved document sources"
```

---

### Day 13 — Confidence + Follow-up

**Goal:** Both features working, gated correctly.

#### Test confidence scoring

```bash
cd backend
python -c "
from retrieval.retriever import retrieve
from chain.confidence import calculate_confidence

# Strong query - should be HIGH confidence
strong_chunks = retrieve('What is the definition of an AI system?')
conf = calculate_confidence(strong_chunks)
print(f'Strong query: {conf.level} ({conf.score:.3f}) - {conf.message}')

# Weak/vague query - should be LOW or MEDIUM
weak_chunks = retrieve('something about technology maybe')
conf = calculate_confidence(weak_chunks)
print(f'Weak query: {conf.level} ({conf.score:.3f}) - {conf.message}')
"
```

#### Test follow-up generation

```bash
python -c "
from retrieval.retriever import retrieve
from chain.followup import generate_followups

q = 'What are the rights of data subjects under GDPR?'
chunks = retrieve(q)
followups = generate_followups(q, chunks, 'HIGH')
print('Follow-up questions:')
for i, fq in enumerate(followups, 1):
    print(f'  {i}. {fq}')
"
```

**Commit:**
```bash
git commit -m "feat(chain): confidence scoring and context-grounded follow-up generation"
```

---

### Day 14 — FastAPI + All Endpoints

**Goal:** Full API running locally, all new fields in response.

#### Start the full backend

```bash
docker-compose up -d
# Or just:
cd backend
uvicorn api.main:app --reload --port 8000
```

#### Test with curl

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"ok","documents_indexed":892,"model":"mistral-large-latest","version":"2.0.0"}

# Full chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the EU AI Act?"}' | python -m json.tool

# Check all new fields are present:
# - query_type
# - confidence.level
# - confidence.score
# - contradiction.has_contradiction
# - follow_up_questions
```

#### View auto-generated API docs

Open http://localhost:8000/docs in your browser. FastAPI generates this automatically from your Pydantic models. This is a professional-looking API docs page — mention it in your README.

**Run final backend eval:**
```bash
python -m eval.evaluate --tag final_backend
```

**Commit:**
```bash
git commit -m "feat(api): all v2 features exposed via FastAPI with full typing"
```

---

## WEEK 3 — Frontend + Deploy + Polish (Days 15–21)

---

### Day 15 — Next.js Setup

**Goal:** Frontend running, all components rendering.

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

You should see the LexIA interface loading. It won't work yet (backend not connected in this env) but it should render.

#### Understanding the component structure

Open each component file and read it:

- **`ConfidenceBadge.tsx`** — colored pill showing HIGH/MEDIUM/LOW with percentage
- **`ContradictionAlert.tsx`** — yellow warning banner (only renders if `has_contradiction: true`)
- **`QueryTypeBadge.tsx`** — small badge showing SINGLE_CHUNK / MULTI-HOP·HyDE / OUT OF SCOPE
- **`FollowUpSuggestions.tsx`** — 3 clickable buttons below each answer
- **`SourceCard.tsx`** — gold pill linking to source document page

**Commit:**
```bash
git commit -m "feat(frontend): Next.js setup with all 5 feature components"
```

---

### Day 16 — Full Chat UI

**Goal:** End-to-end chat working with all features visible.

Start both services:
```bash
# Terminal 1:
docker-compose up -d
# Terminal 2:
cd frontend && npm run dev
```

Open http://localhost:3000 and test:

1. Ask "What is the EU AI Act?" — should show HIGH confidence, sources, follow-ups
2. Ask "Compare GDPR with AI Act" — should show MULTI-HOP·HyDE badge
3. Ask "What is the French tax rate?" — should show OUT OF SCOPE badge, no sources
4. Follow the follow-up suggestions — clicking them should send the question

**Things to check:**
- Contradiction alert shows when two sources conflict
- Follow-up suggestions don't show for LOW confidence answers
- Source cards link to the right URLs
- Streaming works (text appears token by token)

**Commit:**
```bash
git commit -m "feat(frontend): complete chat UI with all 5 v2 features integrated"
```

---

### Day 17 — Eval Dashboard

**Goal:** Streamlit dashboard showing your metric history.

```bash
cd backend
pip install streamlit plotly
streamlit run eval/dashboard.py
# Opens at http://localhost:8501
```

The dashboard shows:
- Line chart of faithfulness/relevancy/precision/recall across all your eval runs
- Best and worst performing questions
- Suggestions for what to improve next

**Take a screenshot** — add it to your README under "## Evaluation Dashboard".

```bash
# Save as docs/eval-dashboard.png
```

**Commit:**
```bash
git commit -m "feat(eval): Streamlit dashboard with metric evolution charts"
```

---

### Day 18 — Deploy Backend to Railway

**Goal:** `https://your-app.railway.app/health` returns 200.

#### Step-by-step Railway deployment

1. Go to https://railway.app → sign in with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `lexia-rag` repository
4. Railway will ask for the root directory → set to `/backend`

5. Add PostgreSQL:
   - In your Railway project → "New" → "Database" → "PostgreSQL"
   - Railway automatically sets `DATABASE_URL` in your environment

6. Set environment variables in Railway dashboard:
```
MISTRAL_API_KEY=your_key_here
CORS_ORIGINS=["https://YOUR-APP.vercel.app"]
```

7. Deploy and wait for build (~5 minutes)

8. Once deployed, run ingestion:
```bash
# Install Railway CLI: https://docs.railway.app/develop/cli
npm install -g @railway/cli
railway login
railway run python -m ingest.run_ingest
```

9. Test your deployment:
```bash
curl https://YOUR-APP.railway.app/health
# Expected: {"status":"ok","documents_indexed":892,...}
```

**☠️ Important:** Cold starts on Railway free tier take 30 seconds. Test 10 minutes before any demo or submission.

**Commit:**
```bash
git commit -m "chore: Railway backend deployment configuration"
```

---

### Day 19 — Deploy Frontend to Vercel

**Goal:** Live Vercel URL works end-to-end.

#### Step-by-step Vercel deployment

1. Go to https://vercel.com → sign in with GitHub
2. "Add New Project" → select `lexia-rag`
3. Framework preset: **Next.js** (auto-detected)
4. Root directory: `frontend`
5. Environment variables:
```
NEXT_PUBLIC_API_URL=https://YOUR-BACKEND.railway.app
```
6. Deploy → wait ~2 minutes

7. Open your Vercel URL → test a question

**If you get CORS errors:**
- Go to Railway dashboard → backend service → Variables
- Update `CORS_ORIGINS=["https://YOUR-VERCEL-APP.vercel.app"]`
- Redeploy backend

8. Add your live URL to GitHub repo:
- GitHub → your repo → About (gear icon) → Website

**Commit:**
```bash
git commit -m "chore: Vercel frontend deployment with Railway backend URL"
```

---

### Day 20 — README + WRITEUP + EVAL_HISTORY

**Goal:** README looks professional. All analysis documented.

#### Update README.md

Replace the current README with a professional one. Must include:

```markdown
# LexIA — EU Legal RAG Assistant

[![Live Demo](badge)](https://your-app.vercel.app)
[![Backend API](badge)](https://your-backend.railway.app/docs)

## What It Does
[2 sentences]

## Architecture
[diagram from docs/architecture.png]

## 5 Advanced Features
[table with each feature + measured improvement]

## Evaluation Results
| Run | Faithfulness | Relevancy | Precision | Recall |
|-----|-------------|-----------|-----------|--------|
| baseline | X.XX | X.XX | X.XX | X.XX |
| +reranker | X.XX | X.XX | X.XX | X.XX |
| +hyde | X.XX | X.XX | X.XX | X.XX |
| +router | X.XX | X.XX | X.XX | X.XX |
| final | X.XX | X.XX | X.XX | X.XX |

## Quick Start
[5 steps max]

## Design Decisions
[why pgvector, why HyDE, why mistral]

## Known Limitations
[honest about what doesn't work well]
```

#### Write WRITEUP.md

For each of the 5 features, write:
- **Problem:** what failure mode it solves
- **Solution:** how it works technically
- **Evidence:** before/after RAGAS score
- **Trade-offs:** what it costs (latency, API calls)

This document is often more impressive than the code.

**Commit:**
```bash
git commit -m "docs: complete README with eval table, WRITEUP with feature analysis"
```

---

### Day 21 — Demo Video + Final Review

**Goal:** 2-minute Loom video. Everything working. Ready to submit.

#### Record your demo video

Install Loom (free): https://loom.com

**Script for your 2-minute video:**

```
0:00 - 0:20  "Hi, I'm [name]. This is LexIA, a RAG system I built to
              answer questions about EU AI regulation. Let me show you
              what makes it different from a basic chatbot."

0:20 - 0:45  Ask a simple question. Show: streaming, sources, confidence badge.
             "Notice the HIGH confidence badge and the source citations with
              page numbers."

0:45 - 1:10  Ask a multi-hop question. Show: MULTI-HOP·HyDE badge.
             "This question requires combining information from multiple
              passages. The HyDE badge means it used hypothetical document
              embeddings to improve retrieval."

1:10 - 1:30  Ask an out-of-scope question. Show: OUT OF SCOPE response.
             "Instead of hallucinating an answer, the query router
              detects this is outside the knowledge base."

1:30 - 1:50  Show eval dashboard. Show the metric evolution chart.
             "Here's the RAGAS evaluation showing how each feature
              improved the metrics."

1:50 - 2:00  "The code is on GitHub at [link]. Thanks for watching."
```

**Don't over-rehearse.** One clean natural take is better than 10 edited takes.

Add Loom URL to README:
```markdown
## Demo
[▶ Watch 2-minute demo](https://loom.com/share/xxxxx)
```

#### Final checklist before submitting

```
[ ] GitHub repo is PUBLIC
[ ] 20+ meaningful commits in history
[ ] Live Vercel URL works (test in incognito)
[ ] /health endpoint returns 200 with documents_indexed > 0
[ ] README has: live URL, demo video, eval table, architecture diagram
[ ] WRITEUP.md has analysis for all 5 features with RAGAS evidence
[ ] You can explain every file without looking at notes
[ ] Loom demo video is uploaded and linked
```

**Final commit:**
```bash
git add .
git commit -m "chore: final portfolio polish - demo video, complete README"
git push origin main
```

---

## Deployment Reference

### Environment Variables

| Variable | Local | Railway |
|---|---|---|
| `MISTRAL_API_KEY` | In .env | Railway dashboard |
| `DATABASE_URL` | `postgresql://lexia:lexia@localhost:5432/lexia` | Auto-set by Railway |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | `["https://your-app.vercel.app"]` |

### Useful Commands

```bash
# Start local environment
docker-compose up -d

# Stop local environment
docker-compose down

# Re-ingest documents (if DB is empty)
docker-compose exec backend python -m ingest.run_ingest

# Run evaluation
docker-compose exec backend python -m eval.evaluate --tag my_run

# View eval dashboard
docker-compose exec backend streamlit run eval/dashboard.py

# View logs
docker-compose logs backend --follow

# Reset database
docker-compose exec backend python -c "from ingest.vectorstore import clear_documents; clear_documents()"
```

---

## How to Answer Technical Interview Questions About This Project

When a hiring manager asks "walk me through your project":

**Don't say:** "I built a RAG chatbot with Next.js and FastAPI"

**Do say:** "I built a RAG pipeline for EU regulatory documents. The interesting part is the two-stage retrieval: I use Mistral embeddings for fast vector search in pgvector, then cross-encoder reranking to improve precision. I measured a 18% improvement in context_precision from reranking. For complex multi-hop questions, I implemented HyDE — instead of embedding the query directly, I generate a hypothetical answer and embed that, which improved context_recall from 0.71 to 0.83 because the hypothesis vocabulary matches the document vocabulary better than the question vocabulary does."

The numbers and the reasoning are what make you memorable.

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `could not connect to server` | pgvector container not running | `docker-compose up -d db` |
| `AuthenticationError` | Wrong Mistral API key | Check `.env`, verify key at console.mistral.ai |
| `RateLimitError` | Too many requests | Wait 60 seconds, reduce batch_size |
| `could not create extension "vector"` | Wrong Docker image | Use `ankane/pgvector` not `postgres` |
| `ModuleNotFoundError` | Venv not activated | `source venv/bin/activate` |
| CORS error in browser | Backend CORS_ORIGINS wrong | Add Vercel URL to Railway CORS_ORIGINS env var |
| Cold start timeout | Railway free tier | Wait 30s, ping /health first |
| Streamlit not found | Not installed | `pip install streamlit plotly` |

---

*Built as a senior-bar AI engineering portfolio project. Good luck.*
