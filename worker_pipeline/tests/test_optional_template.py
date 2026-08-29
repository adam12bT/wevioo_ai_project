from pathlib import Path

from app.models import JobRecord
from app.pipeline_client import PipelineClient


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"run_id": "run-123"}


class _HttpClient:
    def __init__(self):
        self.files = None

    def post(self, path, *, files):
        assert path == "/api/runs"
        self.files = files
        return _Response()


def test_pipeline_client_omits_template_part_when_absent(tmp_path: Path):
    tender = tmp_path / "tender.pdf"
    tender.write_bytes(b"pdf")
    client = object.__new__(PipelineClient)
    client._client = _HttpClient()

    assert client.submit(tender) == "run-123"
    assert set(client._client.files) == {"file"}


def test_job_record_accepts_default_template_path():
    record = JobRecord(
        job_id="job-123",
        tender_filename="tender.pdf",
        created_at=1.0,
        updated_at=1.0,
    )

    assert record.template_filename is None
    assert record.template_path is None
