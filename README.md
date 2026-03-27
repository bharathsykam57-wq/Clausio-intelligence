# Clausio Intelligence - RAG Backend

Production-grade, modularly decoupled Retrieval-Augmented Generation (RAG) backend utilizing FastAPI, PGVector, and Mistral integrations — designed for evaluating exact bounds on EU AI acts and enterprise legislation.

## Architecture Overview
The system follows strict Clean Architecture separations ensuring routing, HTTP middleware, and business services run completely stateless:
1. **API Layer (`/api/routes`)**: Contains pure HTTP endpoints managing `schemas`, authentication constraints, payload parsing, and standard `background_task` delegations. Fast and framework dependent.
2. **Service Layer (`/services`)**: Completely framework-agnostic. Contains natively decoupled `rag_service.py` dictating extraction times, LLM generations, and logging bounds entirely disconnected from dependencies like `HTTPException`.
3. **Retrieval/Chain Core (`/retrieval` & `/chain`)**: Heavily audited embedding arrays managing two-stage retrievals (Cross-Encoder reranking / Vector distance fetching) mapping back to PostgreSQL.

## Features & Evaluation
The infrastructure explicitly traces bounds offline via `scripts/evaluate.py`.
- **Precision@K**: The system scores exact chunk overlaps ensuring correct ground-truth targets are ingested properly during context generation.
- **LLM-as-a-Judge Accuracy**: Uses un-cached Mistral completions scoring (0-5 scale) generated RAG outputs against known truth answers offline.
- **Failure Analysis**: The framework categorizes issues structurally using explicitly designated flags (`user_error`, `model_failure`, `out_of_scope`), dropping specific JSON `extra` traces natively for ELK/Datadog integrations.

## Setup Instructions

**1. Infrastructure Context:**
Require fully activated PostgreSQL database instances utilizing `pgyvector`, and optional `Redis` endpoints natively integrated across `.env`.

**2. Virtual Environment Setup:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Running the API:**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## CLI Usage
A framework-agnostic command line interface operates fully detached from FastAPI for direct internal queries and QA pipeline setups.

```bash
python3 cli.py "What are the penalties for non-compliance with the AI Act?"
```

Optional specific sub-indexing checks:
```bash
python3 cli.py "Will biometric monitoring be allowed in the future?" --source eu_ai_act --no-cache
```

## Trade-offs and Considerations
1. **Coupling LLM Implementations**: Instead of heavily employing large Langchain integrations across the core stack, Mistral is leveraged directly via `mistralai` SDK guaranteeing minimal generation overhead logic and cleaner `latency_generation` mapping in `/services`.
2. **Two-Stage Reranking Costs**: Cross-Encoder accuracy increases `Precision@K` retrieval scores definitively but demands significant compute delay — therefore caching implementations on exact query matches operate aggressively at the route-level ingress.
