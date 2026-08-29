import io

from unittest.mock import AsyncMock, patch


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_rejects_unsupported_extension(client):
    response = client.post(
        "/v1/extract",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 415


def test_extract_rejects_empty_file(client):
    response = client.post(
        "/v1/extract",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 422


def test_extract_rejects_oversized_file(client, monkeypatch):
    from app import main as main_module

    class TinySettings:
        allowed_extensions = (".pdf", ".docx")
        max_file_size_bytes = 10
        max_file_size_mb = 0.00001
        temp_dir = "/tmp/extractor"

        def ensure_temp_dir(self):
            import pathlib

            p = pathlib.Path(self.temp_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p

    monkeypatch.setattr(main_module, "get_settings", lambda: TinySettings())
    response = client.post(
        "/v1/extract",
        files={"file": ("native.pdf", io.BytesIO(b"x" * 100), "application/pdf")},
    )
    assert response.status_code == 413


def test_extract_native_pdf_returns_blocks(client, fixture_path):
    with open(fixture_path("native.pdf"), "rb") as f:
        response = client.post(
            "/v1/extract",
            files={"file": ("native.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["document"]["filename"] == "native.pdf"
    assert len(body["document"]["blocks"]) > 0
    assert body["document"]["metadata"]["page_count"] == 2


def test_extract_docx_returns_blocks(client, fixture_path):
    with open(fixture_path("sample.docx"), "rb") as f:
        response = client.post(
            "/v1/extract",
            files={
                "file": (
                    "sample.docx",
                    f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    types = {b["type"] for b in body["document"]["blocks"]}
    assert "heading" in types
    assert "paragraph" in types
    assert "table" in types


def test_extract_and_index_requires_workspace_slug(client, fixture_path):
    with open(fixture_path("native.pdf"), "rb") as f:
        response = client.post(
            "/v1/extract-and-index",
            files={"file": ("native.pdf", f, "application/pdf")},
            data={"workspace_slug": ""},
        )
    assert response.status_code == 422


def test_extract_and_index_reports_offline_anythingllm(client, fixture_path):
    with patch("app.pipeline.AnythingLLMClient.is_online", new=AsyncMock(return_value=False)):
        with open(fixture_path("native.pdf"), "rb") as f:
            response = client.post(
                "/v1/extract-and-index",
                files={"file": ("native.pdf", f, "application/pdf")},
                data={"workspace_slug": "my-workspace"},
            )
    assert response.status_code == 502
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "anythingllm_offline"


def test_extract_and_index_success(client, fixture_path):
    fake_send_result = {
        "success": True,
        "workspace_slug": "my-workspace",
        "blocks_sent": 2,
        "documents": [{"id": "abc"}],
        "error": None,
    }
    with patch("app.pipeline.AnythingLLMClient.is_online", new=AsyncMock(return_value=True)), patch(
        "app.pipeline.AnythingLLMClient.send_document",
        new=AsyncMock(return_value=__import__("app.models", fromlist=["IndexResult"]).IndexResult(**fake_send_result)),
    ):
        with open(fixture_path("native.pdf"), "rb") as f:
            response = client.post(
                "/v1/extract-and-index",
                files={"file": ("native.pdf", f, "application/pdf")},
                data={"workspace_slug": "my-workspace"},
            )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["index_result"]["blocks_sent"] == 2
