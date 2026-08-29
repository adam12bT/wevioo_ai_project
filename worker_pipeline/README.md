---
title: RFP Pipeline Worker
sdk: docker
app_port: 7860
---

# RFP Pipeline Worker

Independent Celery worker and FastAPI gateway for the existing RFP agent
pipeline. Redis is the Celery broker/result backend and carries replayable SSE
events. A configurable database provider stores job history, document-version
metadata and evaluation reports. Local development uses PostgreSQL (viewable
with pgAdmin); production can use Supabase. A retry resumes a saved upstream
run instead of uploading the same documents twice.

## Architecture

```text
Frontend -------------> FastAPI --enqueue--> Redis --> Celery Worker
                            |                            |
                            | SSE                        | HTTP
                            v                            v
                      Live progress              Agent Pipeline API
                                                         |
                                                         v
       PostgreSQL/Supabase DB <--- jobs/version metadata/evaluations
          Local FS/Supabase Storage <--- inputs/generated documents
```

The Celery workflow executes the pipeline, stores proposal V1/V2/..., runs RAG,
output and performance evaluation in parallel, then aggregates the report.
When the agent API exposes telemetry, performance evaluation uses exact
per-agent durations, attempt history, LLM call counts and provider-reported
token usage. Worker polling timings remain available only as a fallback.

## Database providers

Local PostgreSQL:

```env
DATABASE_PROVIDER=postgres
POSTGRES_PASSWORD=change-me-local-only
DATABASE_URL=postgresql://rfp_worker:change-me-local-only@postgres:5432/rfp_worker
DATABASE_REQUIRED=true
DATABASE_AUTO_CREATE=true
SUPABASE_REQUIRED=false
```

Run `docker compose --profile tools up --build` to include pgAdmin, then open
`http://localhost:5050`. Register a server using host `postgres`, port `5432`,
database/user `rfp_worker`, and the password configured in Compose. pgAdmin is
only a management interface; PostgreSQL is the actual local database.

Production Supabase:

```env
DATABASE_PROVIDER=supabase
DATABASE_REQUIRED=true
SUPABASE_REQUIRED=true
```

Create a project, run `supabase_schema.sql` once in SQL Editor, then configure
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Never expose the service-role
key in the frontend. Supabase Storage holds the uploaded inputs and generated
files, while its PostgreSQL database holds their metadata.

## Run with Docker Compose

1. Copy `.env.example` to `.env`.
2. Set `PIPELINE_BASE_URL` to the existing agent backend.
3. Start the agent backend first.
4. Run `docker compose up --build`.

The worker API is exposed at `http://localhost:8010`. Redis is internal and is
not exposed on the host.

## API

- `POST /api/jobs`: required `file`, optional `template`, and optional `evaluation_dataset` JSON. The agent pipeline uses its versioned built-in template when `template` is omitted.
- `GET /api/jobs`: list recent jobs.
- `GET /api/jobs/{job_id}`: status, stages, progress, and final state.
- `GET /api/jobs/{job_id}/events`: SSE, replayable with `Last-Event-ID`.
- `GET /api/jobs/{job_id}/evaluation`: evaluation report.
- `GET /api/jobs/{job_id}/versions`: persistent V1/V2 history.
- `GET /api/jobs/{job_id}/versions/{version}/download`: older version download.
- `POST /api/jobs/{job_id}/cancel`: cancel a queued or running local job.
- `POST /api/jobs/{job_id}/rerun`: regenerate as the next document version.
- `GET /api/jobs/{job_id}/download`: download the generated Markdown proposal.
- `GET /health`: Redis and upstream pipeline connectivity.

The worker API currently has no authentication. Keep it on a trusted local
network during development; add authentication before a public deployment.

The optional labelled RAG dataset contains a `cases` array. Every case includes
`query`, `section`, and `relevant_chunk_ids`. Without labels, precision and
recall are explicitly marked unavailable rather than fabricated.

## Deployment note

For local use, Compose runs API, Redis, Celery and PostgreSQL separately. On Hugging Face,
the Dockerfile starts FastAPI and one Celery worker in the same container on
port 7860. Configure an external native Redis URL (`rediss://...`) and Supabase
through Space Secrets/Variables.
