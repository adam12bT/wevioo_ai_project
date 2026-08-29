from types import SimpleNamespace

from app.extractors.pdf import _bbox_center_inside, _normalize_ocr_bboxes
from app.extractors.tables import _recover_blank_cells, _rows_to_markdown
from app.models import ExtractionMethod, ParagraphBlock


def test_nan_never_leaks_into_table_markdown():
    markdown = _rows_to_markdown([["Name", float("nan")], ["Alice", 94]])
    assert "nan" not in markdown.casefold()


def test_blank_scanned_cell_is_recovered_from_page_ocr():
    lines = [SimpleNamespace(text="Score", bbox=(75, 5, 95, 20))]
    rows = _recover_blank_cells(
        [["Project", "Language", "Status", float("nan")], ["Atlas", "English", "Done", 94]],
        table_bbox=(0, 0, 100, 50),
        ocr_lines=lines,
    )
    assert rows[0][3] == "Score"


def test_actual_cell_geometry_is_used_for_unequal_columns():
    lines = [SimpleNamespace(text="Score", bbox=(82, 5, 96, 20))]
    rows = _recover_blank_cells(
        [["Project", "Language", "Status", float("nan")]],
        table_bbox=(0, 0, 100, 25),
        ocr_lines=lines,
        cell_bboxes=[
            [(0, 0, 35, 25), (35, 0, 60, 25), (60, 0, 80, 25), (80, 0, 100, 25)]
        ],
    )
    assert rows[0][3] == "Score"


def test_ocr_fragment_inside_table_is_detected_spatially():
    assert _bbox_center_inside((70, 30, 80, 40), (0, 0, 100, 50))
    assert not _bbox_center_inside((70, 60, 80, 70), (0, 0, 100, 50))


def test_ocr_bbox_is_normalized_to_pdf_points():
    block = ParagraphBlock(
        text="OCR text",
        page=1,
        extraction_method=ExtractionMethod.OCR,
        bbox=(100, 200, 300, 400),
    )
    page = SimpleNamespace(width=600, height=800)
    _normalize_ocr_bboxes([block], image_width=1200, image_height=1600, page=page)
    assert block.bbox == (50, 100, 150, 200)
