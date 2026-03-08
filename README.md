# LexIA — EU Legal Intelligence

> Ask questions about the EU AI Act and GDPR. Get grounded, sourced answers — not hallucinations.

🔗 **Live demo:** [clausio-intelligence.vercel.app](https://clausio-intelligence.vercel.app)  
🔗 **API health:** [clausio-intelligence-production.up.railway.app/health](https://clausio-intelligence-production.up.railway.app/health)

---

## Why I built this

EU AI Act compliance is a mess. The regulation is 144 pages of dense legal text, and GDPR is another 88 on top of that. Lawyers and compliance teams are spending hours cross-referencing articles that a well-built RAG system could answer in seconds.

I built LexIA to solve a specific problem: not just retrieval, but *trustworthy* retrieval. Every answer shows the exact source document and page number. Every response includes a confidence score. If the system doesn't have enough context to answer well, it says so instead of making something up.

---

## What it does

You ask a legal question. LexIA figures out what kind of question it is, retrieves the right chunks from the EU AI Act or GDPR corpus, and generates a grounded answer via Mistral Large — streaming token by token, with sources attached.

A question like *"what is the definition of an AI system"* goes through a focused single-chunk retrieval. A question like *"compare GDPR consent requirements with EU AI Act obligations"* triggers a multi-hop pipeline with HyDE query expansion to find semantically richer context. The routing happens automatically — you don't configure anything.

---

## Stack

| Layer | Tech |
|---|---|
| LLM | Mistral Large (via API) |
| Embeddings | mistral-embed (1024-dim) |
| Vector DB | pgvector on PostgreSQL |
| Cache | Redis |
| Backend | FastAPI + SQLAlchemy + Alembic |
| Frontend | Next.js 14 + Tailwind CSS |
| Auth | JWT (HS256) |
| Eval | RAGAS |
| Backend hosting | Railway |
| Frontend hosting | Vercel |
| CI/CD | GitHub Actions |

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────┐
│    Query Router     │  classifies: SINGLE_CHUNK / MULTI_HOP / COMPARATIVE
└────────┬────────────┘
         │
    ┌────▼────┐
    │  HyDE   │  generates hypothetical answer → embeds it → better retrieval
    └────┬────┘
         │
    ┌────▼────────────────────┐
    │   pgvector similarity   │  cosine search, top-6 candidates
    └────┬────────────────────┘
         │
    ┌────▼────────────────────┐
    │   Mistral Large         │  grounded generation, streaming via SSE
    └────┬────────────────────┘
         │
    ┌────▼────────────────────┐
    │   Response              │  answer + confidence score + sources + follow-ups
    └─────────────────────────┘
```

Redis caches repeated queries. Rate limiting runs at 20 req/min and 200 req/day per user, backed by Redis.

---

## Evaluation

I ran RAGAS evals across 5 pipeline iterations to track whether each addition actually helped.

| Run | Faithfulness | Context Precision | Context Recall |
|---|---|---|---|
| baseline | 0.917 | 0.500 | 0.838 |
| with_reranker | 0.679 | 0.625 | 0.738 |
| with_hyde | 0.785 | 0.700 | 0.790 |
| with_router | 0.958 | 0.625 | 0.790 |
| **with_all_features** | **0.844** | **0.567** | **0.637** |

Faithfulness is the metric I care about most here — it measures how grounded the answer is in the retrieved context. For a legal system, fabricating citations is worse than saying "I don't know." The final pipeline sits at 0.844.

The eval dashboard (built in Streamlit) shows metric evolution across runs and surfaces the worst-performing questions — so I know exactly where to focus next rather than optimising blind.

---

## Knowledge base

- **EU Artificial Intelligence Act** — full official text, 398 chunks
- **GDPR/RGPD** — full official text via EUR-Lex, 272 chunks
- **Total:** 670 chunks at 1024-dim embeddings

---

## Features

- **Streaming responses** — SSE, token-by-token, no waiting for full generation
- **Query routing** — single-chunk, multi-hop, and comparative pipelines selected automatically
- **HyDE** — Hypothetical Document Embeddings for better retrieval on vague or abstract questions
- **Source citations** — every answer links to document name and page number
- **Confidence scoring** — HIGH / MEDIUM / LOW based on cosine similarity of retrieved chunks
- **Follow-up questions** — auto-generated to help users go deeper
- **PDF upload** — ingest custom documents at runtime via the UI
- **JWT auth** — register, login, protected endpoints
- **Rate limiting** — Redis-backed, per-user
- **Request logging** — latency, chunk count, confidence tracked on every query
- **RAGAS eval dashboard** — visual metric tracking across pipeline runs

---

## Local setup

**Prerequisites:** Docker, Node.js 18+, Python 3.11+

```bash
# Clone
git clone https://github.com/yourusername/Clausio-intelligence
cd Clausio-intelligence

# Backend env
cp backend/.env.example backend/.env
# Add your MISTRAL_API_KEY to .env

# Start DB + Redis
docker compose up -d db redis

# Install backend deps
cd backend
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Ingest documents (downloads EU AI Act + GDPR automatically)
python -m ingest.run_ingest

# Start backend
uvicorn api.main:app --reload --port 8000
```

```bash
# Frontend (separate terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Frontend runs at `http://localhost:3000`. API docs at `http://localhost:8000/docs`.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT token |
| POST | `/chat/stream` | Streaming RAG query (SSE) |
| POST | `/ingest/upload` | Upload and ingest a PDF |
| GET | `/health` | Service health + document count |

---

## Project structure

```
Clausio-intelligence/
├── backend/
│   ├── api/          # FastAPI app, routes, middleware
│   ├── auth/         # JWT, user models, dependencies
│   ├── chain/        # RAG chain, streaming response builder
│   ├── retrieval/    # Query router, HyDE, retriever
│   ├── ingest/       # PDF loader, embedder, vectorstore
│   ├── cache/        # Redis cache layer
│   ├── db/           # SQLAlchemy session, init, migrations
│   └── eval/         # RAGAS scripts + Streamlit dashboard
├── frontend/
│   ├── app/          # Next.js app router
│   ├── components/   # Chat UI, source cards, confidence badge
│   └── lib/          # API client, auth helpers
└── tests/
    └── unit/         # 23 unit tests
```

---

## Tests

```bash
cd backend
pytest ../tests/unit/ -v
```

23 unit tests across retrieval pipeline, embedder, query router, auth, and rate limiting.

---

## What I'd improve next

**Re-enable the CrossEncoder reranker in production.** It's disabled right now because Railway's free tier has a 4GB Docker image limit and sentence-transformers + torch pushes the image to 8GB. The reranker runs fine locally and improves precision on multi-hop queries. Upgrading to a paid tier fixes this.

**Conversation memory.** Right now every query is stateless. Adding a short-term memory buffer would let users have proper follow-up conversations without re-stating context.

**Expand the corpus.** The current knowledge base covers the main EU texts. Adding national implementation acts and sector-specific guidance would make it genuinely useful for compliance work.

---

## Built with

Mistral AI · pgvector · FastAPI · Next.js · Railway · Vercel · RAGAS
