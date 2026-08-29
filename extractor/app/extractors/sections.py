"""
Section detection.

Walks a flat list of blocks (already produced by the pdf/docx extractors)
and stamps each block with the name of the nearest preceding heading. This
lets downstream consumers (e.g. AnythingLLM) group content by section
without needing to reconstruct document structure themselves.

Headings are recognised in two ways:
  * DOCX: paragraphs already tagged as ContentType.HEADING by the docx
    extractor (based on the Word style name, e.g. "Heading 1").
  * PDF: heuristic — a short line (<= 120 chars), no trailing period, and
    either ALL CAPS, Title Case, or matches a numbered-heading pattern like
    "1.", "1.2", "Chapter 3".
"""
from __future__ import annotations

import re

from app.models import ContentType, ParagraphBlock, TableBlock

_NUMBERED_HEADING_RE = re.compile(r"^(chapter\s+\d+|[0-9]+(\.[0-9]+)*)[\.\)]?\s+\S")
_MAX_HEADING_LEN = 120


def looks_like_heading(text: str) -> bool:
    """Heuristic used for PDF text, which has no style information."""
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LEN:
        return False
    if stripped.endswith((".", ",", ";", ":")):
        return False
    if _NUMBERED_HEADING_RE.match(stripped.lower()):
        return True
    if stripped.isupper() and len(stripped.split()) <= 12:
        return True
    words = stripped.split()
    if 1 < len(words) <= 12:
        capitalized = sum(1 for w in words if w[:1].isupper())
        if capitalized / len(words) >= 0.7:
            return True
    return False


def detect_sections(blocks: list[ParagraphBlock | TableBlock]) -> list[ParagraphBlock | TableBlock]:
    """Mutates and returns `blocks` with `.section` populated on every block.

    For PDF blocks that weren't already classified as headings, this also
    reclassifies paragraphs that look like headings using the heuristic
    above, so callers get consistent behaviour for both file types.
    """
    current_section: str | None = None
    for block in blocks:
        if isinstance(block, ParagraphBlock):
            if block.type != ContentType.HEADING and looks_like_heading(block.text):
                block.type = ContentType.HEADING
                block.heading_level = block.heading_level or 2
            if block.type == ContentType.HEADING:
                current_section = block.text.strip()
        block.section = current_section
    return blocks


def section_count(blocks: list[ParagraphBlock | TableBlock]) -> int:
    return len({b.section for b in blocks if getattr(b, "section", None)})
