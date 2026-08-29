"""
OCR interface.

`run_ocr()` is the single entry point the rest of the pipeline calls. It
dispatches to a concrete engine based on `settings.ocr_engine`. Tesseract is
the default and only engine wired up today; a Surya backend can be added
later by implementing `_ocr_with_surya` without touching any caller.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float | None = None
    lines: list["OCRLine"] | None = None


@dataclass
class OCRLine:
    text: str
    bbox: tuple[float, float, float, float]


def _ocr_with_tesseract(image: "Image", language: str) -> OCRResult:
    import pytesseract

    data = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT)
    grouped: dict[tuple[int, int, int], list[int]] = {}
    for index, word in enumerate(data.get("text", [])):
        if not word.strip():
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        grouped.setdefault(key, []).append(index)

    lines: list[OCRLine] = []
    for indexes in grouped.values():
        line_text = " ".join(data["text"][index].strip() for index in indexes).strip()
        left = min(int(data["left"][index]) for index in indexes)
        top = min(int(data["top"][index]) for index in indexes)
        right = max(int(data["left"][index]) + int(data["width"][index]) for index in indexes)
        bottom = max(int(data["top"][index]) + int(data["height"][index]) for index in indexes)
        lines.append(OCRLine(text=line_text, bbox=(left, top, right, bottom)))
    lines.sort(key=lambda line: (line.bbox[1], line.bbox[0]))
    text = "\n".join(line.text for line in lines)
    confidences = [float(c) for c in data.get("conf", []) if str(c) not in ("-1", "")]
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else None
    return OCRResult(text=text, confidence=avg_conf, lines=lines)


def _ocr_with_surya(image: "Image", language: str) -> OCRResult:  # pragma: no cover
    raise NotImplementedError(
        "Surya OCR support is not wired up yet. Install requirements-ocr.txt "
        "and implement this function, then set OCR_ENGINE=surya."
    )


def run_ocr(image: "Image", language: str | None = None) -> OCRResult:
    """Run OCR on a single rendered page image and return extracted text."""
    settings = get_settings()
    lang = language or settings.ocr_language
    engine = settings.ocr_engine
    try:
        if engine == "tesseract":
            return _ocr_with_tesseract(image, lang)
        if engine == "surya":
            return _ocr_with_surya(image, lang)
        raise ValueError(f"Unknown OCR engine: {engine}")
    except Exception:
        logger.exception("OCR failed for engine=%s", engine)
        return OCRResult(text="", confidence=None, lines=[])


def needs_ocr(native_text: str, min_chars: int | None = None) -> bool:
    """Decide whether a page's native text extraction is too thin to trust."""
    settings = get_settings()
    threshold = min_chars if min_chars is not None else settings.min_native_text_chars
    return len(native_text.strip()) < threshold
