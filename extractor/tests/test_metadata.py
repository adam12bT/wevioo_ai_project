from app.extractors.docx import extract_docx
from app.extractors.sections import detect_sections
from app.models import ContentType
from app.pipeline import run_extraction


def test_docx_blocks_are_stamped_with_sections(fixture_path):
    blocks = extract_docx(fixture_path("sample.docx"))
    blocks = detect_sections(blocks)

    headings = [b for b in blocks if b.type == ContentType.HEADING]
    assert [h.text for h in headings] == ["Introduction", "Data"]

    # Paragraphs after "Introduction" but before "Data" belong to that section.
    intro_paragraphs = [
        b for b in blocks if b.type == ContentType.PARAGRAPH and b.section == "Introduction"
    ]
    assert len(intro_paragraphs) == 2

    # The table appears after the "Data" heading.
    tables = [b for b in blocks if b.type == ContentType.TABLE]
    assert len(tables) == 1
    assert tables[0].section == "Data"


def test_pdf_pipeline_builds_full_metadata(fixture_path):
    document = run_extraction(fixture_path("native.pdf"), "native.pdf", file_size=1234)

    meta = document.metadata
    assert meta.filename == "native.pdf"
    assert meta.file_type == "pdf"
    assert meta.file_size_bytes == 1234
    assert meta.page_count == 2
    assert meta.paragraph_count > 0
    assert meta.table_count >= 1
    assert meta.native_pages == 2
    assert meta.ocr_pages == 0


def test_docx_pipeline_metadata_has_no_page_count(fixture_path):
    document = run_extraction(fixture_path("sample.docx"), "sample.docx", file_size=999)

    assert document.metadata.file_type == "docx"
    assert document.metadata.page_count is None
    assert document.metadata.paragraph_count > 0
    assert document.metadata.table_count == 1
    assert document.metadata.section_count == 2


def test_scanned_pdf_pipeline_reports_ocr_usage(fixture_path):
    document = run_extraction(fixture_path("scanned.pdf"), "scanned.pdf", file_size=555)

    assert document.metadata.ocr_pages == 1
    assert document.metadata.native_pages == 0
    assert all(b.extraction_method.value == "ocr" for b in document.blocks if b.type != "table")


def test_every_block_has_extraction_method(fixture_path):
    document = run_extraction(fixture_path("native.pdf"), "native.pdf", file_size=1)
    for block in document.blocks:
        assert block.extraction_method is not None
