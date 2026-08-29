from app.clients.anythingllm import AnythingLLMClient
from app.config import Settings
from app.models import ContentType, ExtractionMethod, ParagraphBlock, TableBlock

# The only metadata keys AnythingLLM's raw-text ingestion actually persists
# (collector/processRawText/index.js -> METADATA_KEYS.possible, also
# confirmed by GET /v1/document/metadata-schema in the modified AnythingLLM.
# The custom fields below are persisted into document and vector metadata.
ANYTHINGLLM_ACCEPTED_METADATA_KEYS = {
    "url",
    "title",
    "docAuthor",
    "description",
    "docSource",
    "chunkSource",
    "published",
    "externalId",
    "sourceFilename",
    "documentType",
    "page",
    "section",
    "contentType",
    "extractionMethod",
    "layoutOrder",
    "bbox",
}


def _client():
    return AnythingLLMClient(Settings(anythingllm_url="http://fake", anythingllm_api_key=""))


def test_payload_only_uses_accepted_metadata_keys():
    client = _client()
    block = ParagraphBlock(
        type=ContentType.PARAGRAPH,
        text="Some text",
        page=3,
        section="Results",
        extraction_method=ExtractionMethod.OCR,
    )
    payload = client._block_payload("report.pdf", block, "my-workspace")
    assert set(payload["metadata"].keys()) <= ANYTHINGLLM_ACCEPTED_METADATA_KEYS


def test_page_and_section_are_sent_as_structured_metadata():
    client = _client()
    block = ParagraphBlock(
        type=ContentType.PARAGRAPH,
        text="Some text",
        page=3,
        section="Results",
        extraction_method=ExtractionMethod.OCR,
    )
    payload = client._block_payload("report.pdf", block, "my-workspace")

    assert "report.pdf" in payload["metadata"]["title"]
    assert "p.3" in payload["metadata"]["title"]
    assert "Results" in payload["metadata"]["title"]

    assert payload["metadata"]["page"] == 3
    assert payload["metadata"]["section"] == "Results"
    assert payload["metadata"]["contentType"] == "paragraph"
    assert payload["metadata"]["extractionMethod"] == "ocr"
    assert len(payload["metadata"]["externalId"]) == 64


def test_table_block_payload_reports_table_type():
    client = _client()
    block = TableBlock(
        markdown="| a | b |\n| --- | --- |\n| 1 | 2 |",
        page=1,
        table_index=0,
        n_rows=2,
        n_cols=2,
    )
    payload = client._block_payload("report.pdf", block, "ws")
    assert payload["textContent"] == block.markdown
    assert payload["metadata"]["contentType"] == "table"


def test_block_without_page_or_section_still_has_required_title():
    client = _client()
    block = ParagraphBlock(type=ContentType.PARAGRAPH, text="hi", page=None, section=None)
    payload = client._block_payload("sample.docx", block, "ws")
    assert payload["metadata"]["title"] == "sample.docx"
    assert payload["metadata"]["title"]  # never empty - it's a required key server-side


def test_headers_omit_authorization_when_no_api_key():
    client = _client()
    headers = client._headers()
    assert "Authorization" not in headers


def test_headers_include_bearer_token_when_api_key_set():
    client = AnythingLLMClient(Settings(anythingllm_url="http://fake", anythingllm_api_key="secret"))
    headers = client._headers()
    assert headers["Authorization"] == "Bearer secret"
