# RFP Responder — AI-Powered Tender Response Platform

A production-quality frontend for an AI-powered RFP/tender response platform. It connects to existing backend APIs, displays live pipeline progress via Server-Sent Events, handles failures gracefully, and allows users to inspect and download generated proposals.

## Features

- **Dashboard** — Job statistics, average quality scores, RAG precision/recall, recent jobs, and pipeline health summary
- **New Proposal Workflow** — Step-by-step upload with drag-and-drop for tender, template, and optional evaluation dataset
- **Job Workspace** — Real-time pipeline timeline, live template-filling with section-by-section AI generation, and panels for extraction, research, security, quality, evaluation, and version history
- **Active Jobs** — Searchable, filterable, paginated job table
- **Proposal Library** — Completed proposals with quick-access cards
- **Evaluations** — RAG quality, output quality, and performance metrics across all evaluated jobs
- **Knowledge Base** — Manage company documents (CVs, references, certifications) by category with upload and delete
- **System Health** — Real-time status of Redis, Celery, agent pipeline, database, and storage
- **Settings** — API endpoint configuration

## Technology Stack

- React 18 + TypeScript
- Vite 5
- Tailwind CSS 3
- React Router 6
- React Markdown + remark-gfm
- Lucide React icons
- Native EventSource for SSE
- Fetch API for HTTP

## Architecture

```
src/
  api/          # Centralized API client, URL config, and normalization layer
  components/   # Reusable UI components (StatusBadge, ScoreBar, MetricCard, etc.)
  context/      # React context providers (Toast)
  features/     # Feature-specific panels (extraction, research, generation, security, quality, evaluation)
  hooks/        # Custom hooks (useJobs, useJob, useJobEvents, useHealth, useEvaluation, useVersions, useKnowledge)
  layouts/      # Dashboard layout with collapsible sidebar
  pages/        # Route-level page components
  types.ts      # Shared TypeScript types
```

### Key Design Decisions

1. **Normalization Layer** (`src/api/normalize.ts`) — Handles the variety of backend response shapes. The critical rule: generation progress is extracted as `upstream_state.generation_progress || progress.generation || progress || null`. This prevents losing live section data due to incorrect nesting.

2. **Dual Update Strategy** — The job workspace uses both SSE (`useJobEvents`) for immediate updates and polling (`useJob`, every 3 seconds) as a fallback. SSE connections are closed on terminal states and component unmount. The latest server state always wins.

3. **Centralized URL Construction** — All backend URLs are built in `src/api/urls.ts`. Components never construct URLs directly.

4. **Honest Data Presentation** — Unavailable metrics display "Not measured" instead of zero. Security scans that didn't run are clearly stated. Failed jobs are never treated as successful proposals.

5. **Draft Fallback** — When live generation progress is unavailable but `draft_proposal` exists, the workspace splits the markdown by headings and renders the complete draft.

## Environment Variables

Create a `.env` file (see `.env.example`):

```
VITE_WORKER_API_URL=https://adamnouassida5-chroma.hf.space
VITE_AGENT_API_BASE_URL=https://adambouacida7-asistant.hf.space/api
```

- **Worker API** — Manages jobs, generation, evaluation, versions, and downloads
- **Agent API** — Manages the knowledge base

## Local Development

```bash
# Install dependencies
npm install

# Start the dev server (runs automatically in Bolt)
npm run dev

# Type check
npm run typecheck

# Production build
npm run build

# Preview production build
npm run preview
```

## Deployment (Vercel)

1. Push the project to a Git repository (GitHub, GitLab, or Bitbucket).
2. Import the project in [Vercel](https://vercel.com).
3. Add environment variables in the Vercel project settings:
   - `VITE_WORKER_API_URL`
   - `VITE_AGENT_API_BASE_URL`
4. Vercel auto-detects Vite. The build command is `npm run build` and the output directory is `dist`.
5. Deploy.

## API Endpoints Used

### Worker API
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/jobs` | List all jobs |
| POST | `/jobs` | Create a new job (multipart/form-data) |
| GET | `/jobs/{id}` | Get job details |
| GET | `/jobs/{id}/events` | Server-Sent Events stream |
| POST | `/jobs/{id}/cancel` | Cancel a job |
| POST | `/jobs/{id}/rerun` | Rerun a job |
| GET | `/jobs/{id}/evaluation` | Get evaluation data |
| GET | `/jobs/{id}/versions` | List document versions |
| GET | `/jobs/{id}/download` | Download the proposal |
| GET | `/jobs/{id}/versions/{v}/download` | Download a specific version |
| GET | `/health` | System health check |

### Agent API
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/documents` | List knowledge base documents |
| POST | `/documents` | Upload a document (multipart/form-data) |
| DELETE | `/documents/{id}` | Delete a document |
