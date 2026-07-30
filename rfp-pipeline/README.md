# Tender Desk — RFP Pipeline UI

A React UI + FastAPI backend on top of the existing LangGraph pipeline
(Verifier → Extraction → Research → Generation → Quality), backed by
AnythingLLM and GPT Researcher.

Nothing about the original agent logic changed — the 5 agents, `graph.py`,
`state.py`, `anythingllm_client.py`, `company_knowledge.py`, and
`ingest_company_corpus.py` are unmodified. Two things were added:

1. **`agents/` package** — the 5 agent files were moved into an `agents/`
   folder with an `__init__.py` so `graph.py`'s existing
   `from agents import verifier_agent, ...` import works as-is.
2. **`backend/`** — a thin FastAPI layer (`backend/api.py` +
   `backend/run_store.py`) that drives the same `build_graph()` pipeline
   via `.stream()` instead of `.invoke()`, so the UI can show live,
   per-agent progress instead of only a final result.

## Project layout

```
rfp-pipeline/
├── agents/                  # the 5 pipeline nodes (unchanged, just relocated)
│   ├── verifier_agent.py
│   ├── extraction_agent.py
│   ├── research_agent.py
│   ├── generation_agent.py
│   └── quality_agent.py
├── backend/
│   ├── api.py                # FastAPI routes
│   └── run_store.py           # background thread + in-memory run store
├── frontend/                 # React (Vite) UI
│   └── src/
├── graph.py                  # LangGraph wiring (unchanged)
├── state.py                  # RFPState (unchanged)
├── anythingllm_client.py      # (unchanged)
├── company_knowledge.py       # (unchanged)
├── ingest_company_corpus.py   # CLI bulk-ingest script (unchanged, still works)
├── main.py                    # original CLI entry point (still works)
└── requirements.txt
```

## 1. Prerequisites

- The AnythingLLM server running locally (default `http://localhost:3001`)
- GPT Researcher's env vars set — an LLM key/endpoint and a search
  backend (Tavily key, or `RETRIEVER=duckduckgo` for a free option)
- Python 3.10+, Node.js 18+

Copy `.env.example` to `.env` in the project root and adjust as needed —
this is the same file as before, just renamed.

## 2. Backend

```bash
cd rfp-pipeline
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt
uvicorn backend.api:app --reload --port 8000
```

The API is now at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

## 3. Frontend

```bash
cd rfp-pipeline/frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite's dev server proxies `/api/*` to
`http://localhost:8000` (see `vite.config.js`), so there's no CORS setup
needed in dev. For a production build:

```bash
npm run build   # outputs frontend/dist — serve it with any static host,
                 # or point FastAPI's own StaticFiles at it if you prefer
                 # a single-process deployment
```

## What the UI covers

**Pipeline tab**
- Upload a tender (PDF/DOCX) to start a new run
- Run list in the sidebar, with a live status dot per run
- A vertical pipeline rail showing exactly which of the 5 stages is
  active/done/blocked for the selected run, updated by polling
  `GET /api/runs/{id}` every 1.5s while the run is active
- Verification panel — shows the Verifier's blocking reasons if a tender
  fails pre-flight checks (bad format, empty file, etc.)
- Requirements panel — the Extraction agent's structured JSON
  (deliverables, deadlines, budget, evaluation criteria, scope), with a
  graceful fallback view if the model didn't return valid JSON
- Research panel — the Research agent's market/competitor report,
  rendered as Markdown
- Proposal panel — the Generation agent's draft, rendered in a
  document-styled "paper" card, with a retry-attempt counter and a
  **Download .md** button
- Quality panel — word count, missing template sections, the naive PII
  scan results, and pass/fail status (including "hit max retries and
  failed" vs. "queued for another generation pass")

**Knowledge base tab**
- Status and document counts for the 3 persistent company workspaces
  (past proposals, CVs, project references)
- Drag-and-drop upload straight into any of the 3 workspaces (calls the
  same `AnythingLLMClient.upload_document` the CLI ingest script uses)

## Notes / things you may want to change before production

- `run_store.py` keeps runs in memory — fine for a single dev process,
  but restarting the backend loses run history. Swap in Redis/Postgres if
  you need persistence or multiple backend processes.
- CORS is wide open (`allow_origins=["*"]`) for local dev convenience —
  tighten this in `backend/api.py` before exposing it beyond localhost.
- The Quality agent's PII check is still the placeholder regex version
  called out in its own docstring — the UI surfaces exactly what it
  finds today and will pick up LLM Guard's results automatically once
  that's wired in, since the shape of `quality_report` won't change.
