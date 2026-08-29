"""Native and scanned-table extraction utilities.

Native PDF tables are located with pdfplumber so their bounding boxes can be
removed from paragraph extraction and reinserted at the correct reading-order
position. Scanned pages use img2table with bilingual Tesseract OCR.
"""
from __future__ import annotations

import logging
import math
import tempfile
from numbers import Real
from pathlib import Path
from typing import Iterable

import pdfplumber

from app.config import get_settings
from app.models import ExtractionMethod, ExtractionWarning, TableBlock

logger = logging.getLogger(__name__)


def _clean_cell(cell: object | None) -> str:
    """Return safe Markdown text without leaking pandas/NumPy NaN values."""
    if cell is None:
        return ""
    if isinstance(cell, Real) and math.isnan(float(cell)):
        return ""
    return str(cell).strip().replace("\n", " ").replace("|", "\\|")


def _rows_to_markdown(rows: list[list[object | None]]) -> str:
    cleaned = [
        [_clean_cell(cell) for cell in row]
        for row in rows
    ]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if not cleaned:
        return ""
    header, *body = cleaned
    n_cols = len(header)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * n_cols) + " |",
    ]
    for row in body:
        padded = row + [""] * (n_cols - len(row))
        lines.append("| " + " | ".join(padded[:n_cols]) + " |")
    return "\n".join(lines)


def extract_native_page_tables(page, page_number: int) -> list[TableBlock]:
    """Extract tables and their PDF coordinates from one pdfplumber page."""
    blocks: list[TableBlock] = []
    for table_index, table in enumerate(page.find_tables()):
        rows = table.extract() or []
        markdown = _rows_to_markdown(rows)
        if not markdown:
            continue
        blocks.append(
            TableBlock(
                markdown=markdown,
                page=page_number,
                table_index=table_index,
                extraction_method=ExtractionMethod.NATIVE,
                n_rows=len(rows),
                n_cols=max((len(row) for row in rows), default=0),
                bbox=tuple(float(value) for value in table.bbox),
            )
        )
    return blocks


def _recover_blank_cells(
    rows: list[list[object | None]],
    table_bbox: tuple[float, float, float, float] | None,
    ocr_lines: Iterable | None,
    cell_bboxes: list[list[tuple[float, float, float, float] | None]] | None = None,
    image=None,
    language: str | None = None,
) -> list[list[str]]:
    """Use page-level OCR to recover cells missed by img2table's OCR pass.

    img2table can correctly locate a grid while missing one short cell such as
    ``Score``. For blank cells, use the line whose center lies inside the
    corresponding grid region. This is deliberately conservative: populated
    cells are never replaced.
    """
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows]
    if not cleaned or not table_bbox or (not ocr_lines and image is None):
        return cleaned

    row_count = len(cleaned)
    column_count = max((len(row) for row in cleaned), default=0)
    if not row_count or not column_count:
        return cleaned
    for row in cleaned:
        row.extend([""] * (column_count - len(row)))

    left, top, right, bottom = table_bbox
    cell_width = (right - left) / column_count
    cell_height = (bottom - top) / row_count
    lines = [
        line for line in (ocr_lines or []) if getattr(line, "text", "").strip()
    ]

    for row_index, row in enumerate(cleaned):
        for column_index, value in enumerate(row):
            if value:
                continue
            exact_bbox = None
            if cell_bboxes and row_index < len(cell_bboxes):
                row_boxes = cell_bboxes[row_index]
                if column_index < len(row_boxes):
                    exact_bbox = row_boxes[column_index]
            if exact_bbox:
                x0, y0, x1, y1 = exact_bbox
            else:
                x0 = left + column_index * cell_width
                x1 = left + (column_index + 1) * cell_width
                y0 = top + row_index * cell_height
                y1 = top + (row_index + 1) * cell_height
            candidates = []
            for line in lines:
                lx0, ly0, lx1, ly1 = line.bbox
                center_x = (lx0 + lx1) / 2
                center_y = (ly0 + ly1) / 2
                if x0 <= center_x <= x1 and y0 <= center_y <= y1:
                    candidates.append(line)
            if candidates:
                candidates.sort(key=lambda line: (line.bbox[1], line.bbox[0]))
                row[column_index] = " ".join(line.text.strip() for line in candidates)
                continue

            # The full-page OCR pass may miss a short word in a bordered cell.
            # Crop that exact cell and use Tesseract's single-line mode, which
            # is substantially more reliable for isolated table headers.
            if image is not None and language:
                recovered = _ocr_cell_crop(image, (x0, y0, x1, y1), language)
                if recovered:
                    row[column_index] = recovered
    return cleaned


def _ocr_cell_crop(
    image,
    bbox: tuple[float, float, float, float],
    language: str,
) -> str:
    import pytesseract
    from PIL import ImageOps

    left, top, right, bottom = bbox
    inset = max(2, int(min(right - left, bottom - top) * 0.04))
    crop_box = (
        max(0, int(left) + inset),
        max(0, int(top) + inset),
        min(image.width, int(right) - inset),
        min(image.height, int(bottom) - inset),
    )
    if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
        return ""

    crop = image.crop(crop_box).convert("L")
    crop = ImageOps.autocontrast(crop)
    # Upscaling helps short headers while retaining accents.
    crop = crop.resize((crop.width * 2, crop.height * 2))
    for page_segmentation_mode in (7, 6):
        text = pytesseract.image_to_string(
            crop,
            lang=language,
            config=f"--psm {page_segmentation_mode}",
        )
        cleaned = " ".join(text.split()).strip("|[]{} ")
        if cleaned:
            return cleaned
    return ""


def _cell_bboxes(table) -> list[list[tuple[float, float, float, float] | None]]:
    """Return img2table cell geometry in row/column order."""
    rows = []
    for _, cells in table.content.items():
        row = []
        for cell in cells:
            bbox = getattr(cell, "bbox", None)
            row.append(
                tuple(float(getattr(bbox, key)) for key in ("x1", "y1", "x2", "y2"))
                if bbox is not None
                else None
            )
        rows.append(row)
    return rows


def extract_scanned_page_tables(
    image, page_number: int, language: str, ocr_lines: Iterable | None = None
) -> list[TableBlock]:
    """Recognize table structure on a rendered scanned page.

    img2table is imported lazily so native-only documents still work when the
    optional scanned-table dependency is not installed.
    """
    from img2table.document import Image as Img2TableImage
    from img2table.ocr import TesseractOCR

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        image.save(temp_path, format="PNG")
        document = Img2TableImage(src=str(temp_path))
        ocr = TesseractOCR(lang=language, n_threads=1)
        extracted = document.extract_tables(
            ocr=ocr,
            implicit_rows=True,
            implicit_columns=True,
            borderless_tables=True,
            min_confidence=45,
        )
        blocks: list[TableBlock] = []
        for table_index, table in enumerate(extracted):
            dataframe = table.df
            bbox = getattr(table, "bbox", None)
            coords = None
            if bbox is not None:
                coords = tuple(
                    float(getattr(bbox, key)) for key in ("x1", "y1", "x2", "y2")
                )
            rows = _recover_blank_cells(
                dataframe.values.tolist(),
                coords,
                ocr_lines,
                cell_bboxes=_cell_bboxes(table),
                image=image,
                language=language,
            )
            markdown = _rows_to_markdown(rows)
            if not markdown:
                continue
            blocks.append(
                TableBlock(
                    markdown=markdown,
                    page=page_number,
                    table_index=table_index,
                    extraction_method=ExtractionMethod.OCR,
                    n_rows=dataframe.shape[0],
                    n_cols=dataframe.shape[1],
                    bbox=coords,
                    is_scanned=True,
                )
            )
        return blocks
    finally:
        temp_path.unlink(missing_ok=True)


def extract_tables(file_path: str) -> tuple[list[TableBlock], list[ExtractionWarning]]:
    """Compatibility helper for callers that only want native PDF tables."""
    warnings: list[ExtractionWarning] = []
    blocks: list[TableBlock] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                blocks.extend(extract_native_page_tables(page, page_number))
        return blocks, warnings
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Table extraction failed")
        warnings.append(ExtractionWarning(code="table_extraction_failed", message=str(exc)))
        return [], warnings
