import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.models import JobRecord


logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Small REST client for private Storage and durable Postgres records."""

    def __init__(self) -> None:
        if not settings.supabase_enabled:
            raise RuntimeError("Supabase is not configured")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }
        self._client = httpx.Client(
            base_url=settings.supabase_url,
            headers=self._headers,
            timeout=settings.supabase_request_timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> bool:
        response = self._client.get(
            "/rest/v1/worker_jobs",
            params={"select": "job_id", "limit": "1"},
        )
        response.raise_for_status()
        return True

    def upload_bytes(
        self,
        object_key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        encoded = quote(object_key, safe="/")
        response = self._client.post(
            f"/storage/v1/object/{settings.supabase_storage_bucket}/{encoded}",
            headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
            content=content,
        )
        response.raise_for_status()
        return object_key

    def upload_file(
        self,
        object_key: str,
        source: Path,
        content_type: str = "application/octet-stream",
    ) -> str:
        return self.upload_bytes(object_key, source.read_bytes(), content_type)

    def download_bytes(self, object_key: str) -> bytes:
        encoded = quote(object_key, safe="/")
        response = self._client.get(
            f"/storage/v1/object/authenticated/"
            f"{settings.supabase_storage_bucket}/{encoded}"
        )
        response.raise_for_status()
        return response.content

    def upsert_job(self, record: JobRecord) -> None:
        payload = {
            "job_id": record.job_id,
            "status": record.status.value,
            "tender_filename": record.tender_filename,
            "template_filename": record.template_filename,
            "tender_path": record.tender_path,
            "template_path": record.template_path,
            "evaluation_path": record.evaluation_path,
            "upstream_run_id": record.upstream_run_id,
            "celery_task_id": record.celery_task_id,
            "current_stage": record.current_stage,
            "completed_stages": record.completed_stages,
            "progress": record.progress,
            "tender_object_key": record.tender_object_key,
            "template_object_key": record.template_object_key,
            "evaluation_object_key": record.evaluation_object_key,
            "result_object_key": record.result_object_key,
            "result_path": record.result_path,
            "document_version": record.document_version,
            "upstream_terminal_status": record.upstream_terminal_status,
            "stage_timings": record.stage_timings,
            "evaluation_results": record.evaluation_results,
            "upstream_state": record.upstream_state,
            "error": record.error,
            "created_at_epoch": record.created_at,
            "updated_at_epoch": record.updated_at,
        }
        response = self._client.post(
            "/rest/v1/worker_jobs",
            params={"on_conflict": "job_id"},
            headers={**self._headers, "Prefer": "resolution=merge-duplicates"},
            json=payload,
        )
        response.raise_for_status()

    def get_job(self, job_id: str) -> JobRecord | None:
        response = self._client.get(
            "/rest/v1/worker_jobs",
            params={"job_id": f"eq.{job_id}", "select": "*", "limit": "1"},
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        row = rows[0]
        return JobRecord(
            job_id=row["job_id"],
            status=row["status"],
            tender_filename=row["tender_filename"],
            template_filename=row["template_filename"],
            tender_path=row.get("tender_path"),
            template_path=row.get("template_path"),
            evaluation_path=row.get("evaluation_path"),
            tender_object_key=row.get("tender_object_key"),
            template_object_key=row.get("template_object_key"),
            evaluation_object_key=row.get("evaluation_object_key"),
            created_at=float(row["created_at_epoch"]),
            updated_at=float(row["updated_at_epoch"]),
            upstream_run_id=row.get("upstream_run_id"),
            celery_task_id=row.get("celery_task_id"),
            current_stage=row.get("current_stage"),
            completed_stages=row.get("completed_stages") or [],
            progress=row.get("progress"),
            result_object_key=row.get("result_object_key"),
            result_path=row.get("result_path"),
            document_version=row.get("document_version"),
            upstream_terminal_status=row.get("upstream_terminal_status"),
            stage_timings=row.get("stage_timings") or {},
            evaluation_results=row.get("evaluation_results") or {},
            upstream_state=row.get("upstream_state"),
            error=row.get("error"),
        )

    def list_jobs(self, limit: int) -> list[JobRecord]:
        response = self._client.get(
            "/rest/v1/worker_jobs",
            params={
                "select": "*",
                "order": "created_at_epoch.desc",
                "limit": str(limit),
            },
        )
        response.raise_for_status()
        records: list[JobRecord] = []
        for row in response.json():
            record = self.get_job(row["job_id"])
            if record:
                records.append(record)
        return records

    def next_document_version(self, job_id: str) -> int:
        response = self._client.get(
            "/rest/v1/document_versions",
            params={
                "job_id": f"eq.{job_id}",
                "select": "version",
                "order": "version.desc",
                "limit": "1",
            },
        )
        response.raise_for_status()
        rows = response.json()
        return int(rows[0]["version"]) + 1 if rows else 1

    def save_document_version(
        self,
        job_id: str,
        version: int,
        object_key: str,
        checksum: str,
        size_bytes: int,
    ) -> None:
        response = self._client.post(
            "/rest/v1/document_versions",
            headers={**self._headers, "Prefer": "return=minimal"},
            json={
                "job_id": job_id,
                "version": version,
                "object_key": object_key,
                "checksum_sha256": checksum,
                "size_bytes": size_bytes,
            },
        )
        response.raise_for_status()

    def list_document_versions(self, job_id: str) -> list[dict[str, Any]]:
        response = self._client.get(
            "/rest/v1/document_versions",
            params={
                "job_id": f"eq.{job_id}",
                "select": "version,object_key,checksum_sha256,size_bytes,created_at",
                "order": "version.desc",
            },
        )
        response.raise_for_status()
        return list(response.json())

    def get_document_version(self, job_id: str, version: int) -> dict[str, Any] | None:
        response = self._client.get(
            "/rest/v1/document_versions",
            params={
                "job_id": f"eq.{job_id}",
                "version": f"eq.{version}",
                "select": "version,object_key,checksum_sha256,size_bytes,created_at",
                "limit": "1",
            },
        )
        response.raise_for_status()
        rows = response.json()
        return dict(rows[0]) if rows else None

    def save_evaluation(
        self,
        job_id: str,
        document_version: int | None,
        evaluation: dict[str, Any],
    ) -> None:
        response = self._client.post(
            "/rest/v1/evaluation_reports",
            params={"on_conflict": "job_id,document_version"},
            headers={**self._headers, "Prefer": "resolution=merge-duplicates"},
            json={
                "job_id": job_id,
                "document_version": document_version or 0,
                "report": evaluation,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        response.raise_for_status()


def supabase_repository() -> SupabaseRepository | None:
    return SupabaseRepository() if settings.supabase_enabled else None
