---
title: AnythingLLM Document Extractor
emoji: "📄"
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
---

# AnythingLLM Document Extraction Service

A standalone FastAPI microservice that extracts structured, per-block
content (paragraphs, headings, tables) from PDF and DOCX files — preserving
page numbers, section headings, and how each block was extracted (native
text vs. OCR) — and can optionally push that content straight into an
AnythingLLM workspace via its `raw-text` upload API.

It runs independently of AnythingLLM (including a modified/forked
instance) and only talks to it over HTTP, so the two can be deployed,
scaled, and versioned separately.

## Why per-block extraction instead of one big string?

Most extraction pipelines flatten a document into a single blob of text
before indexing it. This service instead returns a list of blocks — each
one a paragraph, heading, or table — with its own metadata:

- **Page** the block came from (PDF only)
- **Section** — the nearest preceding heading
- **Content type** — `paragraph`, `heading`, or `table`
- **Extraction method** — `native` or `ocr`

That metadata survives the trip into AnythingLLM (as per-document metadata
on each `raw-text` upload), so downstream retrieval/citations can point back
to "page 4, Results section" instead of just "somewhere in this file."

## Architecture

```
app/
├── main.py                FastAPI app: /health, /v1/extract, /v1/extract-and-index
├── config.py               Environment-driven settings (pydantic-settings)
├── models.py                Pydantic response models
├── pipeline.py             Orchestrates the steps below
├── extractors/
│   ├── pdf.py               Native text via pdfplumber, OCR fallback per page
│   ├── docx.py              Paragraphs/headings/tables in document order
│   ├── ocr.py                Tesseract today; pluggable for Surya later
│   ├── tables.py             pdfplumber or Camelot → Markdown tables
│   └── sections.py           Heading detection + section tagging
└── clients/
    └── anythingllm.py       POST /api/v1/document/raw-text, one call per block
```

Pipeline steps (`pipeline.run_extraction`):

1. Detect file type from the extension (`.pdf` / `.docx`).
2. Extract every page (PDF) or walk the body in order (DOCX).
3. OCR any PDF page whose native text is too thin (`MIN_NATIVE_TEXT_CHARS`).
4. Extract tables (PDF: pdfplumber/Camelot; DOCX: python-docx tables).
5. Detect section headings and stamp every block with its section.
6. Build document-level metadata (page/paragraph/table/OCR counts).
7. Return the blocks, or (via `run_extraction_and_index`) send them to
   AnythingLLM.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# System packages needed for OCR / PDF rasterization:
#   Debian/Ubuntu: sudo apt-get install tesseract-ocr poppler-utils ghostscript
#   macOS:         brew install tesseract poppler ghostscript

cp .env.example .env   # then edit ANYTHINGLLM_URL / ANYTHINGLLM_API_KEY
uvicorn app.main:app --reload
```

Optional heavier OCR engine (Surya):

```bash
pip install -r requirements.txt -r requirements-ocr.txt
# then set OCR_ENGINE=surya in .env
```

## Configuration

All settings are environment variables (see `.env.example` for the full
list with defaults), the important ones being:

| Variable | Purpose |
|---|---|
| `MAX_FILE_SIZE_MB` | Reject uploads larger than this |
| `OCR_LANGUAGE` | Tesseract language code, e.g. `eng` |
| `MIN_NATIVE_TEXT_CHARS` | Below this many native chars on a page, OCR runs instead |
| `TABLE_EXTRACTION_ENGINE` | `pdfplumber` (default, no extra deps) or `camelot` |
| `ANYTHINGLLM_URL` | Base URL of your AnythingLLM instance |
| `ANYTHINGLLM_API_KEY` | Optional. Leave blank if your instance has API-key auth disabled (see below); if set, it's sent as a Bearer token |
| `REQUEST_TIMEOUT_SECONDS` | Timeout for the service's own HTTP handlers |
| `TEMP_DIR` | Where uploads are written while being processed |

## API

### `GET /health`

```json
{"status": "ok"}
```

### `POST /v1/extract`

Multipart form upload, field name `file`. Returns extracted blocks without
touching AnythingLLM.

```bash
curl -X POST http://localhost:8000/v1/extract \
  -F "file=@report.pdf"
```

```json
{
  "success": true,
  "document": {
    "filename": "report.pdf",
    "metadata": {
      "filename": "report.pdf",
      "file_type": "pdf",
      "file_size_bytes": 48213,
      "page_count": 3,
      "paragraph_count": 12,
      "table_count": 1,
      "section_count": 4,
      "ocr_pages": 1,
      "native_pages": 2
    },
    "pages": [
      {"page_number": 1, "native_char_count": 812, "used_ocr": false, "ocr_confidence": null}
    ],
    "blocks": [
      {
        "type": "heading",
        "text": "Results",
        "page": 2,
        "section": "Results",
        "extraction_method": "native",
        "heading_level": 2
      },
      {
        "type": "table",
        "markdown": "| Name | Score |\n| --- | --- |\n| Alice | 90 |",
        "page": 2,
        "section": "Results",
        "table_index": 0,
        "extraction_method": "native",
        "n_rows": 3,
        "n_cols": 2
      }
    ],
    "warnings": []
  },
  "error": null
}
```

### `POST /v1/extract-and-index`

Same upload, plus a required `workspace_slug` form field. Extracts, then
sends every block to AnythingLLM's `raw-text` endpoint as a separate
"document," tagged with page/section/content-type/extraction-method
metadata, and adds each to the given workspace.

```bash
curl -X POST http://localhost:8000/v1/extract-and-index \
  -F "file=@report.pdf" \
  -F "workspace_slug=research-notes"
```

```json
{
  "success": true,
  "document": { "...": "same shape as /v1/extract" },
  "index_result": {
    "success": true,
    "workspace_slug": "research-notes",
    "blocks_sent": 17,
    "documents": [ { "id": "...", "location": "custom-documents/..." } ],
    "error": null
  },
  "error": null
}
```

If AnythingLLM isn't reachable, this returns HTTP 502 with
`error.code = "anythingllm_offline"` and still includes the extracted
`document` so nothing already computed is lost.

## AnythingLLM integration

This service is a client of AnythingLLM's document API — it doesn't need
to run inside the same repo or process. It calls:

```
POST {ANYTHINGLLM_URL}/api/v1/document/raw-text
Authorization: Bearer {ANYTHINGLLM_API_KEY}   # only sent if ANYTHINGLLM_API_KEY is set
Content-Type: application/json

{
  "textContent": "<block text or table markdown>",
  "addToWorkspaces": "<workspace_slug>",
  "metadata": {
    "title": "report.pdf — p.2 — Results",
    "docSource": "extractor://report.pdf",
    "description": "type=paragraph | extraction_method=native | page=2 | section=Results"
  }
}
```

One call is made per block, so a 20-paragraph document results in 20
AnythingLLM documents, each individually addressable/citable.

### Why the metadata is shaped this way

This was the main thing worth reading the target AnythingLLM fork for.
`POST /v1/document/raw-text` *looks* like it accepts arbitrary metadata,
but tracing the request through `collector/processRawText/index.js` shows
it only keeps a fixed whitelist of keys (`METADATA_KEYS.possible`): `url`,
`title`, `docAuthor`, `description`, `docSource`, `chunkSource`,
`published` — the same 7 keys hardcoded in
`GET /v1/document/metadata-schema`. Anything else (a raw `page` or
`section` key, for instance) is silently dropped before it's ever written
to disk, so an earlier version of this client that sent those as their own
keys was quietly losing that metadata on arrival.

Of that whitelist, only `title` is guaranteed to reach the LLM as context —
`TextSplitter.buildHeaderMeta()` prepends it to every chunk as
`sourceDocument`. So this client bakes page/section location directly into
`title` (e.g. `report.pdf — p.2 — Results`), and writes a second,
machine-parseable copy into `description` (`type=... | extraction_method=... |
page=... | section=...`) for anything reading the stored document JSON or
Chroma's per-chunk vector metadata directly — `description` isn't
LLM-prepended, but it does survive into both. `docSource` is set to
`extractor://<filename>` so every block from the same upload can be traced
back to its source file.

If your fork changes `METADATA_KEYS.possible` in `processRawText.js` to
accept more keys, or you'd rather encode this differently, the only place
that needs to change is `app/clients/anythingllm.py::_block_payload`.

### Auth-disabled forks

If your AnythingLLM fork has removed API-key auth (e.g. `validApiKey`
middleware in `server/utils/middleware/validApiKey.js` reduced to a no-op
`next()` with no check — as in the fork this service was built against),
just leave `ANYTHINGLLM_API_KEY` unset in `.env`. This client only attaches
an `Authorization` header when a key is actually configured, so requests
go out with no auth header at all in that case, and it still works
unmodified against a stock instance that does enforce keys.

## Docker

```bash
docker compose up --build
```

By default `docker-compose.yml` assumes AnythingLLM is already running
elsewhere and reachable at `ANYTHINGLLM_URL` (override via a `.env` file
or exported env vars). To run your modified AnythingLLM fork from the same
compose file, uncomment the `anythingllm` service block in
`docker-compose.yml` and point its `build.context` at your checkout.

## GitHub Actions deployment to Hugging Face

The workflow in `.github/workflows/ci-cd.yml` runs the Python tests and a
production Docker build for pull requests and pushes to `main`. After a
successful `main` build, it mirrors the repository to a Hugging Face Docker
Space. A failed test or Docker build prevents deployment.

Configure the GitHub repository under **Settings > Secrets and variables >
Actions**:

1. Add the repository secret `HF_TOKEN`. Use a fine-grained Hugging Face token
   with write access only to the extractor Space.
2. Add the repository variable `HF_SPACE_ID`, for example
   `adambouacida7/document-extractor`.

Use a separate Space from the AnythingLLM deployment. The extractor calls the
hosted AnythingLLM API; deploying it over the AnythingLLM Space would replace
that service. The Space is configured as Docker and exposes port `8000` via
the README metadata above.

If the hosted AnythingLLM API requires authentication, add
`ANYTHINGLLM_API_KEY` as a secret in the Hugging Face Space settings. The
default `ANYTHINGLLM_URL` points to
`https://adambouacida7-ai-cv.hf.space`; it can also be overridden as a Space
variable.

## Current extraction and indexing behavior

- OCR uses both English and French by default (`OCR_LANGUAGE=eng+fra`). The
  Docker image installs both Tesseract language packs.
- Native PDF words that fall inside detected table boxes are excluded from
  paragraph blocks, preventing the same table from being indexed twice.
- PDF paragraphs and tables carry `layout_order` and `bbox`, and are emitted
  in top-to-bottom page layout order.
- Scanned pages use Tesseract for text and `img2table` for scanned-table
  recognition. Set `SCANNED_TABLE_EXTRACTION_ENABLED=false` to disable it.
- Extraction and upload writes run in worker threads so OCR, PDF parsing, and
  disk I/O do not block FastAPI's event loop.
- Every block sent to AnythingLLM includes structured `page`, `section`,
  `contentType`, `documentType`, `extractionMethod`, `layoutOrder`, `bbox`, `sourceFilename`,
  and deterministic `externalId` metadata. This requires the accompanying
  changes in the modified AnythingLLM checkout.
- The AnythingLLM client retries transient network, rate-limit, timeout, and
  server errors with exponential backoff. Repeated indexing is idempotent via
  `externalId`; partial new indexing is removed from the workspace when a
  later block fails and rollback is enabled.

The earlier metadata explanation describes the stock AnythingLLM limitation.
In this project, the modified AnythingLLM collector, API schema, vector
metadata response, and chunk header preserve the custom fields directly.

## Tests

```bash
pip install -r requirements.txt
python tests/fixtures/generate_fixtures.py   # only needed if fixtures are missing/changed
pytest -q
```

- `tests/test_api.py` — health check, upload validation, response shapes,
  `extract-and-index` behavior when AnythingLLM is offline vs. reachable
  (mocked).
- `tests/test_pdf.py` — native-only, scanned-only (OCR), and mixed PDFs;
  page numbers; table extraction.
- `tests/test_metadata.py` — section detection, per-block extraction
  method, document-level metadata for both PDF and DOCX.
- `tests/fixtures/` — small generated PDF/DOCX files; regenerate with
  `tests/fixtures/generate_fixtures.py` if you need to change them.
