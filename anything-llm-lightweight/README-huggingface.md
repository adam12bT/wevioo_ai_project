---
title: AnythingLLM Lightweight (RAG API)
emoji: 📄
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# AnythingLLM — lightweight, headless fork

Backend-only (no frontend) AnythingLLM fork: document ingestion (PDF/DOCX/XLSX/OCR),
Chroma vector store, and connections to LLM providers, exposed purely as a REST API.

The document splitter defaults to chunks of 512 tokens with an overlap of
50 tokens. Existing values stored under `text_splitter_chunk_size` and
`text_splitter_chunk_overlap` take precedence over these defaults.

There is no web UI here — interact with it via the API. See `/api-docs` once
running (or the endpoint files under `server/endpoints/`) for the available routes.

⚠️ **Storage on the free tier is ephemeral.** Without the Persistent Storage
add-on, the SQLite DB, uploaded documents, and Chroma vector data are wiped
every time this Space rebuilds (any `git push`, or a manual restart/factory
reboot). Good for demos and testing; not for production data you care about.
