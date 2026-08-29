"""
FastAPI application exposing the document extraction service.

Endpoints
---------
GET  /health                  liveness/readiness probe
POST /v1/extract              upload a file, get back structured blocks
POST /v1/extract-and-index    upload a file, extract, then push into AnythingLLM
"""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.models import ExtractAndIndexResponse, ExtractionError, ExtractResponse
from app.pipeline import UnsupportedFileTypeError, run_extraction, run_extraction_and_index

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AnythingLLM Document Extraction Service",
    description="Extracts structured, per-block text/tables from PDF and DOCX files, "
    "optionally indexing them directly into an AnythingLLM workspace.",
    version="1.0.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _validate_upload(file: UploadFile, content: bytes) -> None:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=422, detail="Uploaded file has no filename.")

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file extension '{ext}'. Allowed: {list(settings.allowed_extensions)}",
        )

    if len(content) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.max_file_size_mb} MB.",
        )


async def _save_upload(file: UploadFile, content: bytes) -> str:
    settings = get_settings()
    temp_dir = settings.ensure_temp_dir()
    _, ext = os.path.splitext(file.filename)
    dest = temp_dir / f"{uuid.uuid4().hex}{ext}"
    def write_upload() -> None:
        with open(dest, "wb") as f:
            f.write(content)

    await run_in_threadpool(write_upload)
    return str(dest)


@app.post("/v1/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)):
    content = await file.read()
    _validate_upload(file, content)

    saved_path = await _save_upload(file, content)
    try:
        document = await run_in_threadpool(run_extraction, saved_path, file.filename, len(content))
        return ExtractResponse(success=True, document=document)
    except UnsupportedFileTypeError as exc:
        return JSONResponse(
            status_code=415,
            content=ExtractResponse(
                success=False, error=ExtractionError(code="unsupported_file_type", message=str(exc))
            ).model_dump(),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Extraction failed for %s", file.filename)
        return JSONResponse(
            status_code=500,
            content=ExtractResponse(
                success=False, error=ExtractionError(code="extraction_failed", message=str(exc))
            ).model_dump(),
        )
    finally:
        _cleanup(saved_path)


@app.post("/v1/extract-and-index", response_model=ExtractAndIndexResponse)
async def extract_and_index(file: UploadFile = File(...), workspace_slug: str = Form(...)):
    content = await file.read()
    _validate_upload(file, content)

    if not workspace_slug.strip():
        raise HTTPException(status_code=422, detail="workspace_slug is required.")

    saved_path = await _save_upload(file, content)
    try:
        result = await run_extraction_and_index(
            saved_path, file.filename, len(content), workspace_slug
        )
        status_code = 200 if result.success else 502
        return JSONResponse(status_code=status_code, content=result.model_dump())
    finally:
        _cleanup(saved_path)


def _cleanup(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
