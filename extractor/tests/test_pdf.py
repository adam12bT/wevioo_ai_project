from app.extractors.pdf import extract_pdf
from app.extractors.tables import extract_tables
from app.models import ExtractionMethod, ParagraphBlock, TableBlock


def test_native_pdf_extracts_text_without_ocr(fixture_path):
    blocks, pages, warnings = extract_pdf(fixture_path("native.pdf"))

    assert len(pages) == 2
    assert all(not p.used_ocr for p in pages)
    assert all(b.extraction_method == ExtractionMethod.NATIVE for b in blocks)
    joined = " ".join(b.text for b in blocks if isinstance(b, ParagraphBlock))
    assert "INTRODUCTION" in joined
    assert "first paragraph" in joined


def test_scanned_pdf_falls_back_to_ocr(fixture_path):
    blocks, pages, warnings = extract_pdf(fixture_path("scanned.pdf"))

    assert len(pages) == 1
    assert pages[0].used_ocr is True
    assert any(b.extraction_method == ExtractionMethod.OCR for b in blocks)
    joined = " ".join(b.text for b in blocks if isinstance(b, ParagraphBlock)).lower()
    # OCR isn't pixel-perfect, so check for a substring rather than exact match.
    assert "scanned" in joined or "heading" in joined


def test_mixed_pdf_uses_native_and_ocr_per_page(fixture_path):
    blocks, pages, warnings = extract_pdf(fixture_path("mixed.pdf"))

    assert len(pages) == 2
    assert pages[0].used_ocr is False
    assert pages[1].used_ocr is True

    page1_blocks = [b for b in blocks if b.page == 1]
    page2_blocks = [b for b in blocks if b.page == 2]
    assert all(b.extraction_method == ExtractionMethod.NATIVE for b in page1_blocks)
    assert any(b.extraction_method == ExtractionMethod.OCR for b in page2_blocks)


def test_native_table_text_is_not_duplicated_as_paragraphs(fixture_path):
    blocks, _, _ = extract_pdf(fixture_path("native.pdf"))
    paragraph_text = " ".join(
        block.text for block in blocks if isinstance(block, ParagraphBlock)
    )
    tables = [block for block in blocks if isinstance(block, TableBlock)]
    assert tables
    assert not ("Name" in paragraph_text and "Score" in paragraph_text)


def test_blocks_follow_layout_order(fixture_path):
    blocks, _, _ = extract_pdf(fixture_path("native.pdf"))
    assert [block.layout_order for block in blocks] == list(range(len(blocks)))


def test_page_numbers_are_preserved(fixture_path):
    blocks, pages, _ = extract_pdf(fixture_path("native.pdf"))
    pages_seen = {b.page for b in blocks}
    assert pages_seen == {1, 2}


def test_table_extraction_on_native_pdf(fixture_path):
    tables, warnings = extract_tables(fixture_path("native.pdf"))
    assert len(tables) >= 1
    table = tables[0]
    assert table.page == 2
    assert "Name" in table.markdown
    assert "Score" in table.markdown
    assert table.n_rows >= 2
