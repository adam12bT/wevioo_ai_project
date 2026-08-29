"""
Response / data models shared across the pipeline, extractors and API layer.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"


class ExtractionMethod(str, Enum):
    NATIVE = "native"
    OCR = "ocr"


class ParagraphBlock(BaseModel):
    """A single paragraph or heading of text extracted from the document."""

    type: ContentType = ContentType.PARAGRAPH
    text: str
    page: Optional[int] = Field(default=None, description="1-indexed page number, None for DOCX without pages")
    section: Optional[str] = Field(default=None, description="Nearest preceding heading, if any")
    extraction_method: ExtractionMethod = ExtractionMethod.NATIVE
    heading_level: Optional[int] = Field(default=None, description="1-6 when type == heading")
    layout_order: int = Field(default=0, description="Reading order within the document")
    bbox: Optional[tuple[float, float, float, float]] = Field(
        default=None, description="PDF coordinates: left, top, right, bottom"
    )


class TableBlock(BaseModel):
    """A table extracted from the document, rendered to Markdown."""

    type: ContentType = ContentType.TABLE
    markdown: str
    page: Optional[int] = None
    section: Optional[str] = None
    table_index: int = Field(description="0-indexed position of this table on its page")
    extraction_method: ExtractionMethod = ExtractionMethod.NATIVE
    n_rows: int = 0
    n_cols: int = 0
    layout_order: int = Field(default=0, description="Reading order within the document")
    bbox: Optional[tuple[float, float, float, float]] = None
    is_scanned: bool = False


class PageInfo(BaseModel):
    """Per-page bookkeeping, mainly useful for PDFs."""

    page_number: int
    native_char_count: int = 0
    used_ocr: bool = False
    ocr_confidence: Optional[float] = None


class ExtractionWarning(BaseModel):
    code: str
    message: str
    page: Optional[int] = None


class ExtractionError(BaseModel):
    code: str
    message: str
    detail: Optional[str] = None


class DocumentMetadata(BaseModel):
    filename: str
    file_type: str  # "pdf" | "docx"
    file_size_bytes: int
    content_sha256: str = ""
    page_count: Optional[int] = None
    paragraph_count: int = 0
    table_count: int = 0
    section_count: int = 0
    ocr_pages: int = 0
    native_pages: int = 0


class ExtractedDocument(BaseModel):
    """Top-level result of running the extraction pipeline on a single file."""

    filename: str
    metadata: DocumentMetadata
    pages: list[PageInfo] = Field(default_factory=list)
    blocks: list[ParagraphBlock | TableBlock] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class IndexResult(BaseModel):
    """Result of pushing an extracted document's blocks into AnythingLLM."""

    success: bool
    workspace_slug: str
    blocks_sent: int
    documents: list[dict] = Field(default_factory=list)
    skipped_existing: int = 0
    rolled_back: int = 0
    error: Optional[str] = None


class ExtractResponse(BaseModel):
    success: bool
    document: Optional[ExtractedDocument] = None
    error: Optional[ExtractionError] = None


class ExtractAndIndexResponse(BaseModel):
    success: bool
    document: Optional[ExtractedDocument] = None
    index_result: Optional[IndexResult] = None
    error: Optional[ExtractionError] = None
