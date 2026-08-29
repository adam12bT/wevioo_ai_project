"""Layout-aware PDF extraction with per-page OCR fallback.

Native table rectangles are excluded from word extraction, preventing table
content from appearing twice. Text lines and tables are then merged using
their vertical coordinates. Scanned pages use bilingual OCR and optionally
img2table for row/column recognition.
"""
from __future__ import annotations

import logging
import re

import pdfplumber

from app.config import get_settings
from app.extractors.ocr import needs_ocr, run_ocr
from app.extractors.tables import extract_native_page_tables, extract_scanned_page_tables
from app.models import ContentType, ExtractionMethod, ExtractionWarning, PageInfo, ParagraphBlock, TableBlock

logger = logging.getLogger(__name__)


def _inside_bbox(word: dict, bbox: tuple[float, float, float, float]) -> bool:
    center_x = (float(word["x0"]) + float(word["x1"])) / 2
    center_y = (float(word["top"]) + float(word["bottom"])) / 2
    left, top, right, bottom = bbox
    return left <= center_x <= right and top <= center_y <= bottom


def _native_text_blocks(page, page_number: int, table_blocks: list[TableBlock]) -> list[ParagraphBlock]:
    """Build ordered text lines while excluding words located inside tables."""
    table_boxes = [table.bbox for table in table_blocks if table.bbox]
    words = [
        word
        for word in page.extract_words(use_text_flow=True, keep_blank_chars=False)
        if not any(_inside_bbox(word, bbox) for bbox in table_boxes)
    ]
    lines: list[list[dict]] = []
    tolerance = 3.0
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not lines or abs(float(word["top"]) - float(lines[-1][0]["top"])) > tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)

    blocks: list[ParagraphBlock] = []
    for line in lines:
        ordered = sorted(line, key=lambda item: float(item["x0"]))
        text = " ".join(str(word["text"]).strip() for word in ordered).strip()
        if not text:
            continue
        blocks.append(
            ParagraphBlock(
                type=ContentType.PARAGRAPH,
                text=text,
                page=page_number,
                extraction_method=ExtractionMethod.NATIVE,
                bbox=(
                    min(float(word["x0"]) for word in ordered),
                    min(float(word["top"]) for word in ordered),
                    max(float(word["x1"]) for word in ordered),
                    max(float(word["bottom"]) for word in ordered),
                ),
            )
        )
    return blocks


def _normalized_terms(text: str) -> set[str]:
    return {term for term in re.findall(r"(?u)\b\w{2,}\b", text.casefold())}


def _line_is_table_duplicate(text: str, tables: list[TableBlock]) -> bool:
    terms = _normalized_terms(text)
    if not terms:
        return False
    table_terms = set().union(*(_normalized_terms(table.markdown) for table in tables)) if tables else set()
    return len(terms & table_terms) / len(terms) >= 0.8


def _bbox_center_inside(
    bbox: tuple[float, float, float, float],
    container: tuple[float, float, float, float],
) -> bool:
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2
    return container[0] <= center_x <= container[2] and container[1] <= center_y <= container[3]


def _ocr_page_blocks(image, page_number: int, settings, warnings):
    ocr_result = run_ocr(image, settings.ocr_language)
    tables: list[TableBlock] = []
    if settings.scanned_table_extraction_enabled:
        try:
            tables = extract_scanned_page_tables(
                image,
                page_number,
                settings.ocr_language,
                ocr_lines=ocr_result.lines,
            )
        except Exception as exc:
            logger.warning("Scanned-table recognition failed on page %s: %s", page_number, exc)
            warnings.append(
                ExtractionWarning(
                    code="scanned_table_extraction_failed",
                    message=f"Scanned-table recognition failed: {exc}",
                    page=page_number,
                )
            )

    text_blocks: list[ParagraphBlock] = []
    table_boxes = [table.bbox for table in tables if table.bbox]
    for line in ocr_result.lines or []:
        if any(_bbox_center_inside(line.bbox, bbox) for bbox in table_boxes):
            continue
        if _line_is_table_duplicate(line.text, tables):
            continue
        text_blocks.append(
            ParagraphBlock(
                text=line.text,
                page=page_number,
                extraction_method=ExtractionMethod.OCR,
                bbox=line.bbox,
            )
        )
    return [*text_blocks, *tables], ocr_result


def _normalize_ocr_bboxes(blocks, image_width: int, image_height: int, page) -> None:
    """Convert rendered-image pixel boxes to the same PDF-point units as native boxes."""
    if not image_width or not image_height:
        return
    x_scale = float(page.width) / float(image_width)
    y_scale = float(page.height) / float(image_height)
    for block in blocks:
        if not block.bbox:
            continue
        left, top, right, bottom = block.bbox
        block.bbox = (
            left * x_scale,
            top * y_scale,
            right * x_scale,
            bottom * y_scale,
        )


def _sort_and_number(blocks: list[ParagraphBlock | TableBlock], starting_order: int) -> int:
    blocks.sort(key=lambda block: ((block.bbox or (0, float("inf"), 0, 0))[1], (block.bbox or (0, 0, 0, 0))[0]))
    for offset, block in enumerate(blocks):
        block.layout_order = starting_order + offset
    return starting_order + len(blocks)


def extract_pdf(file_path: str) -> tuple[list[ParagraphBlock | TableBlock], list[PageInfo], list[ExtractionWarning]]:
    settings = get_settings()
    all_blocks: list[ParagraphBlock | TableBlock] = []
    pages: list[PageInfo] = []
    warnings: list[ExtractionWarning] = []
    next_order = 0

    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            native_text = page.extract_text() or ""
            page_info = PageInfo(page_number=page_number, native_char_count=len(native_text.strip()))

            if needs_ocr(native_text, settings.min_native_text_chars):
                rendered = page.to_image(resolution=settings.ocr_dpi).original
                page_blocks, result = _ocr_page_blocks(rendered, page_number, settings, warnings)
                _normalize_ocr_bboxes(
                    page_blocks,
                    image_width=rendered.width,
                    image_height=rendered.height,
                    page=page,
                )
                page_info.used_ocr = True
                page_info.ocr_confidence = result.confidence
            else:
                tables = extract_native_page_tables(page, page_number)
                page_blocks = [*_native_text_blocks(page, page_number, tables), *tables]

            next_order = _sort_and_number(page_blocks, next_order)
            if not page_blocks:
                warnings.append(
                    ExtractionWarning(
                        code="empty_page",
                        message="Page produced no extractable text or table content.",
                        page=page_number,
                    )
                )
            all_blocks.extend(page_blocks)
            pages.append(page_info)

    return all_blocks, pages, warnings
