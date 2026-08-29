<div align="center">

# AI-Powered RFP Proposal Platform

### From tender upload to an evidence-grounded, evaluated and versioned proposal

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-OpenAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-5B3FD6)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant-DC244C?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Docker](https://img.shields.io/badge/Containers-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

**Multi-agent orchestration · RAG · asynchronous workers · live progress · automated evaluation**

Developed by **Adam Bouassida** during an AI Engineering internship at **Wevioo**.

</div>

---

## Overview

This repository contains an end-to-end platform for turning tender documents into structured proposal drafts. It accepts a tender and an optional client response template, extracts the document structure, researches the market, retrieves company evidence, generates each proposal section, evaluates the result and stores versioned outputs.

The platform is designed around one central rule:

> Tender requirements, company evidence and external research are different sources of truth and must never be treated as interchangeable.

When bidder evidence is unavailable, the system records a visible evidence gap instead of inventing a project, person, certification or commercial commitment.

## Highlights

- **Dynamic templates** — follows the uploaded response template; falls back to a versioned built-in template when none is supplied.
- **Seven-stage agent pipeline** — verification, extraction, research, retrieval, generation, security and quality.
- **Evidence-aware RAG** — retrieves tender chunks, CVs, project references and past proposals through AnythingLLM and Qdrant.
- **Structured document extraction** — PDF, DOCX, bilingual OCR, headings, page metadata and Markdown table recovery.
- **Asynchronous execution** — Celery workers use Redis for tasks, results, retries and replayable progress events.
- **Live experience** — the React application combines Server-Sent Events with polling fallback.
- **Automated evaluation** — RAG precision/recall proxies, context relevance, context utilization, template compliance, groundedness, coherence and performance timings.
- **Evidence traceability** — the quality reviewer receives the exact evidence supplied to generation.
- **Targeted repair** — failed retries regenerate only affected sections while preserving accepted content.
- **Durable history** — Supabase/PostgreSQL stores jobs, evaluation reports and document-version metadata; object storage keeps uploads and outputs.
- **Deployment-ready** — Docker, GitHub Actions, Hugging Face Spaces and Vercel.

## Architecture

<p align="center">
  <img width="1024" height="1536" alt="Design sans titre" src="https://github.com/user-attachments/assets/698246d0-d9c3-40ca-beb7-b906818bce05" />

</p>

The diagram is also available as an [editable SVG](docs/architecture/microservice-architecture.svg).

### Runtime communication

| From | To | Communication | Purpose |
|---|---|---|---|
| React frontend | Worker API | HTTPS, REST, multipart | Upload tender, template and optional evaluation data |
| Worker API | Frontend | SSE + JSON polling | Stream progress and recover the latest job state |
| FastAPI worker | Celery | Task enqueue | Move long-running work outside the request lifecycle |
| Celery | Upstash/local Redis | `rediss://` / `redis://` | Broker, results, events and retry coordination |
| Celery worker | Agent API | `POST /api/runs` + polling | Start and monitor a proposal run |
| Agent pipeline | Extractor | Multipart HTTP | Extract PDF/DOCX content and metadata |
| Extractor | AnythingLLM | Raw-text HTTP API | Index structured blocks into isolated workspaces |
| Agent pipeline | AnythingLLM | RAG query API | Retrieve evidence-bearing chunks |
| AnythingLLM | Qdrant | Vector search | Store embeddings and return ranked matches |
| Agent pipeline | LLM/research providers | HTTPS | Generate, research and evaluate |
| Worker service | Supabase/PostgreSQL | REST/SQL | Persist jobs, evaluation reports and versions |
| Worker service | Supabase Storage/local disk | Object/file storage | Persist uploads, proposals and reports |

## Agent workflow

```text
Tender + optional template
          │
          ▼
     1. Verification
          │
          ▼
      2. Extraction
          │
          ▼
       3. Research
          │
          ▼
      4. Retrieval
          │
          ▼
      5. Generation
          │
          ▼
       6. Security
          │
          ▼
        7. Quality
          │
          ▼
Versioned proposal + evaluation report
```

| Stage | Responsibility | Primary output |
|---|---|---|
| **Verification** | Validate uploads, create isolated workspaces and prepare ingestion | Verified run and workspace identifiers |
| **Extraction** | Derive scope, requirements, constraints, deadlines and template sections | Structured requirement model |
| **Research** | Gather external market context and validate its relevance to the tender | Cited research summary |
| **Retrieval** | Retrieve section-specific tender and company evidence | Ranked chunks with provenance |
| **Generation** | Draft template-aligned sections while neutralizing unsupported claims | Complete Markdown proposal |
| **Security** | Apply configured content/PII scanning and report scanner availability honestly | Security report |
| **Quality** | Check structure, groundedness, coherence and contradictions against exact evidence | Quality decision and repair feedback |

## Evaluation framework

The worker evaluates each completed run across three dimensions.

### RAG quality

- Precision proxy
- Recall proxy
- F1 score
- Context relevance
- Context utilization
- Per-section retrieved and used chunks
- Optional labelled evaluation dataset support

### Output quality

- Response-template compliance
- Required-section coverage and order
- Groundedness against tender and company evidence
- Cross-section coherence
- Unsupported-claim and contradiction detection
- Explicit non-scoring warnings for disclosed evidence gaps
- Optional LLM Guard scanning when enabled

### Performance

- Per-agent duration
- Generation-attempt history
- Pipeline throughput
- LLM request counts
- Provider-reported prompt and completion tokens

Unavailable measurements are displayed as **Not measured** rather than silently converted to zero.

## Repository layout

```text
.
├── agent_pipeline/             LangGraph agents, RAG orchestration and Agent API
├── worker_pipeline/            FastAPI gateway, Celery, SSE, evaluation and versioning
├── extractor/                  PDF/DOCX/OCR extraction and AnythingLLM indexing
├── anything-llm-lightweight/   Modified AnythingLLM service and Qdrant integration
├── front_end/                  React + TypeScript + Vite dashboard
└── docs/
    └── architecture/           PNG and editable SVG architecture diagrams
```

Detailed documentation is available inside each service:

- [Agent pipeline](agent_pipeline/README.md)
- [Worker pipeline](worker_pipeline/README.md)
- [Document extractor](extractor/README.md)
- [AnythingLLM service](anything-llm-lightweight/README.md)
- [Frontend](front_end/README.md)

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router, React Markdown |
| APIs | FastAPI, Pydantic, OpenAPI, Uvicorn |
| Agent orchestration | LangGraph |
| Background execution | Celery, Redis / Upstash Redis |
| RAG | AnythingLLM, Qdrant, reranking, structured retrieval traces |
| Extraction | pdfplumber, python-docx, Tesseract OCR, Camelot/img2table support |
| LLMs | Groq GPT-OSS in hosted mode; Ollama in local mode |
| Research | GPT Researcher, DDGS/Tavily-compatible configuration |
| Persistence | PostgreSQL or Supabase, Supabase Object Storage or local filesystem |
| Delivery | Docker, GitHub Actions, Hugging Face Spaces, Vercel |

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- An AnythingLLM instance configured to use Qdrant
- An LLM provider: Groq for hosted use or Ollama for local development

### 1. Configure the services

Create environment files from the provided examples:

```bash
cp agent_pipeline/.env.example agent_pipeline/.env
cp worker_pipeline/.env.example worker_pipeline/.env
cp extractor/.env.example extractor/.env
cp front_end/.env.example front_end/.env
```

On PowerShell, use `Copy-Item` instead of `cp`.

At minimum, configure:

| Service | Variables |
|---|---|
| Agent pipeline | `LLM_PROVIDER`, provider key, `ANYTHINGLLM_BASE_URL`, `EXTRACTOR_BASE_URL` |
| Extractor | `ANYTHINGLLM_URL`, optional `ANYTHINGLLM_API_KEY`, OCR settings |
| Worker | `REDIS_URL`, `PIPELINE_BASE_URL`, database/storage provider |
| Frontend | `VITE_WORKER_API_URL`, `VITE_AGENT_API_BASE_URL` |

Never commit `.env` files or expose `SUPABASE_SERVICE_ROLE_KEY` in the frontend.

### 2. Start AnythingLLM and Qdrant

Configure the included AnythingLLM service to use Qdrant, then start it using the instructions in [anything-llm-lightweight/README.md](anything-llm-lightweight/README.md).

Recommended retrieval settings:

- Chunk size: approximately 512 tokens
- Chunk overlap: approximately 50 tokens
- Separate workspaces for the tender, template, CVs, project references and past proposals

### 3. Start the extractor

```bash
cd extractor
docker compose up --build
```

The extractor is available at `http://localhost:8007`; health check: `GET /health`.

### 4. Start the agent pipeline

```bash
cd agent_pipeline
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -e ".[full]"
uvicorn rfp.api.app:app --host 0.0.0.0 --port 8000
```

Health check: `GET http://localhost:8000/api/health`.

### 5. Start the worker stack

Set this value in `worker_pipeline/.env` when the agent API runs on the host:

```env
PIPELINE_BASE_URL=http://host.docker.internal:8000
```

Then start Redis, PostgreSQL, the API and the Celery worker:

```bash
cd worker_pipeline
docker compose up --build
```

The worker API is available at `http://localhost:8010`; health check: `GET /health`.

To include pgAdmin:

```bash
docker compose --profile tools up --build
```

### 6. Start the frontend

```bash
cd front_end
npm install
npm run dev
```

Open `http://localhost:5173`.

## Create a proposal

Use the frontend, or submit files directly to the worker API:

```bash
curl -X POST http://localhost:8010/api/jobs \
  -F "file=@tender.pdf" \
  -F "template=@response-template.docx"
```

The `template` field is optional. When omitted, the agent pipeline uses its built-in versioned template.

Follow progress with SSE:

```bash
curl -N http://localhost:8010/api/jobs/JOB_ID/events
```

## API map

### Worker API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jobs` | Create a job from a tender, optional template and optional evaluation dataset |
| `GET` | `/api/jobs` | List recent jobs |
| `GET` | `/api/jobs/{job_id}` | Read current state and progress |
| `GET` | `/api/jobs/{job_id}/events` | Subscribe to replayable SSE events |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel queued/running work |
| `POST` | `/api/jobs/{job_id}/rerun` | Generate the next document version |
| `GET` | `/api/jobs/{job_id}/evaluation` | Read the aggregated evaluation |
| `GET` | `/api/jobs/{job_id}/versions` | List persistent versions |
| `GET` | `/api/jobs/{job_id}/download` | Download the latest proposal |
| `GET` | `/health` | Check Redis, database, storage and upstream health |

### Agent API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/runs` | Start an agent-pipeline run |
| `GET` | `/api/runs` | List in-process runs |
| `GET` | `/api/runs/{run_id}` | Read run state and telemetry |
| `GET` | `/api/runs/{run_id}/download` | Download the generated proposal |
| `GET` | `/api/knowledge` | List knowledge-base documents |
| `POST` | `/api/knowledge/{category}/upload` | Add company evidence |
| `GET` | `/api/health` | Read pipeline stages and scanner capabilities |

Interactive OpenAPI documentation is exposed at `/docs` by each FastAPI service.

## Company knowledge

The company corpus is separated into three evidence classes:

```text
agent_pipeline/company_corpus/
├── cvs/
├── project_references/
└── past_proposals/
```

Ingest it with:

```bash
cd agent_pipeline
python ingest_company_corpus.py
```

Repeated ingestion skips identical content through a local manifest. Past proposals primarily guide structure and style; they are not automatically treated as proof of present capability.

## Testing and verification

```bash
# Agent pipeline
cd agent_pipeline
pytest -q
python -m rfp.compatibility_cli --replay-only

# Worker pipeline
cd ../worker_pipeline
pytest -q

# Extractor
cd ../extractor
pytest -q

# Frontend
cd ../front_end
npm run typecheck
npm run lint
npm run build
```

For real extraction/RAG validation, see `agent_pipeline/phase2_smoke_test.py` and the service-specific README files.

## Deployment

The production topology uses independently deployable services:

- **Vercel** — React frontend
- **Hugging Face Space** — worker API and Celery worker
- **Hugging Face Space** — agent pipeline API
- **Hugging Face Space** — document extractor
- **AnythingLLM + Qdrant** — knowledge and vector retrieval
- **Upstash Redis** — external Celery broker/result backend
- **Supabase** — durable PostgreSQL metadata and object storage

GitHub Actions validates each service and builds its Docker image before deployment. Configure secrets in GitHub and the target platforms—never in committed files.

## Security notes

- The worker API currently has no authentication. Keep it behind a trusted boundary until authentication and authorization are added.
- Supabase service-role credentials belong only in backend secrets.
- The health API reports whether LLM Guard and fallback scanners actually ran.
- No-scanner states are displayed explicitly; they are not reported as successful security scans.
- Use synthetic or approved documents for demonstrations and public screenshots.

## Design principles

1. **Evidence before confidence** — unsupported bidder claims are removed or disclosed.
2. **Dynamic over hard-coded** — proposal structure follows the selected template.
3. **Honest evaluation** — unavailable measurements are never fabricated.
4. **Traceable generation** — exact retrieved evidence is preserved for review.
5. **Durable orchestration** — long-running jobs, events and versions survive the request lifecycle.
6. **Independent services** — extraction, knowledge, agents, workers and UI can evolve separately.

## Author

**Adam Bouassida**  
AI Engineering internship project developed at **Wevioo**.

If this project is useful to you, consider starring the repository or opening an issue with feedback.

