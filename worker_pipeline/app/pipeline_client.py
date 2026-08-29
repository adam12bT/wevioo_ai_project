from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx

from app.config import settings


class PipelineClient:
    def __init__(self) -> None:
        headers = {}
        if settings.pipeline_api_key:
            headers["Authorization"] = f"Bearer {settings.pipeline_api_key}"
        self._client = httpx.Client(
            base_url=settings.pipeline_base_url,
            headers=headers,
            timeout=httpx.Timeout(settings.pipeline_request_timeout_seconds),
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> dict[str, Any]:
        response = self._client.get("/api/health")
        response.raise_for_status()
        return response.json()

    def submit(self, tender_path: Path, template_path: Path | None = None) -> str:
        with ExitStack() as stack:
            tender = stack.enter_context(tender_path.open("rb"))
            files = {"file": (tender_path.name, tender, "application/octet-stream")}
            if template_path is not None:
                template = stack.enter_context(template_path.open("rb"))
                files["template"] = (
                    template_path.name,
                    template,
                    "application/octet-stream",
                )
            response = self._client.post(
                "/api/runs",
                files=files,
            )
        response.raise_for_status()
        run_id = response.json().get("run_id")
        if not run_id:
            raise RuntimeError("Pipeline accepted the request without returning run_id")
        return str(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        response = self._client.get(f"/api/runs/{run_id}")
        response.raise_for_status()
        return response.json()

    def download(self, run_id: str) -> bytes:
        response = self._client.get(f"/api/runs/{run_id}/download")
        response.raise_for_status()
        return response.content
