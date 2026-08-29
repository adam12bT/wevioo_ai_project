"""
Coordinates the full extraction process for a single uploaded file:

  1. Detect file type from extension.
  2. Extract every page (native text, OCR-ing pages that need it).
  3. Merge text and tables in PDF layout order.
  4. Detect sections and stamp them onto every block.
  5. Build metadata and a stable content hash.
  6. Return an ExtractedDocument, optionally pushed to AnythingLLM.
"""
from __future__ import annotations

import hashlib
import logging
import os

from starlette.concurrency import run_in_threadpool

from app.clients.anythingllm import AnythingLLMClient
from app.config import get_settings
from app.extractors.docx import extract_docx
from app.extractors.pdf import extract_pdf
from app.extractors.sections import detect_sections, section_count
from app.models import (
    DocumentMetadata,
    ExtractAndIndexResponse,
    ExtractedDocument,
    ExtractionError,
    ExtractionMethod,
    ExtractResponse,
    IndexResult,
    ParagraphBlock,
    TableBlock,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}


class UnsupportedFileTypeError(Exception):
    pass


def detect_file_type(filename: str) -> str:
    _, ext = os.path.splitext(filename.lower())
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file extension '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return SUPPORTED_EXTENSIONS[ext]


def _build_metadata(filename: str, file_type: str, file_size: int, blocks, pages) -> DocumentMetadata:
    paragraph_count = sum(1 for b in blocks if isinstance(b, ParagraphBlock))
    table_count = sum(1 for b in blocks if isinstance(b, TableBlock))
    ocr_pages = sum(1 for p in pages if p.used_ocr)
    return DocumentMetadata(
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        content_sha256="",
        page_count=len(pages) or None,
        paragraph_count=paragraph_count,
        table_count=table_count,
        section_count=section_count(blocks),
        ocr_pages=ocr_pages,
        native_pages=max(len(pages) - ocr_pages, 0) if pages else 0,
    )


def run_extraction(file_path: str, filename: str, file_size: int) -> ExtractedDocument:
    """Run the full extraction pipeline on a file already saved to disk."""
    file_type = detect_file_type(filename)
    warnings = []

    if file_type == "pdf":
        blocks, pages, pdf_warnings = extract_pdf(file_path)
        warnings.extend(pdf_warnings)
    else:  # docx
        blocks = extract_docx(file_path)
        pages = []

    blocks = detect_sections(blocks)
    metadata = _build_metadata(filename, file_type, file_size, blocks, pages)
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    metadata.content_sha256 = digest.hexdigest()

    return ExtractedDocument(
        filename=filename,
        metadata=metadata,
        pages=pages,
        blocks=blocks,
        warnings=warnings,
    )


async def run_extraction_and_index(
    file_path: str, filename: str, file_size: int, workspace_slug: str
) -> ExtractAndIndexResponse:
    """Run extraction, then push the resulting blocks into AnythingLLM."""
    try:
        document = await run_in_threadpool(run_extraction, file_path, filename, file_size)
    except UnsupportedFileTypeError as exc:
        return ExtractAndIndexResponse(
            success=False,
            error=ExtractionError(code="unsupported_file_type", message=str(exc)),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Extraction failed for %s", filename)
        return ExtractAndIndexResponse(
            success=False,
            error=ExtractionError(code="extraction_failed", message=str(exc)),
        )

    client = AnythingLLMClient(get_settings())
    if not await client.is_online():
        return ExtractAndIndexResponse(
            success=False,
            document=document,
            index_result=IndexResult(success=False, workspace_slug=workspace_slug, blocks_sent=0, error="AnythingLLM is not reachable"),
            error=ExtractionError(code="anythingllm_offline", message="AnythingLLM is not reachable at the configured URL."),
        )

    index_result = await client.send_document(document, workspace_slug)
    return ExtractAndIndexResponse(
        success=index_result.success,
        document=document,
        index_result=index_result,
        error=None if index_result.success else ExtractionError(code="index_failed", message=index_result.error or "Unknown error"),
    )
