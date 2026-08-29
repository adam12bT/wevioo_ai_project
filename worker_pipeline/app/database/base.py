from typing import Any, Protocol

from app.models import JobRecord


class DatabaseRepository(Protocol):
    """Operations required from every durable database provider."""

    def close(self) -> None: ...

    def health(self) -> bool: ...

    def upsert_job(self, record: JobRecord) -> None: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

    def list_jobs(self, limit: int) -> list[JobRecord]: ...

    def next_document_version(self, job_id: str) -> int: ...

    def save_document_version(
        self,
        job_id: str,
        version: int,
        object_key: str,
        checksum: str,
        size_bytes: int,
    ) -> None: ...

    def list_document_versions(self, job_id: str) -> list[dict[str, Any]]: ...

    def get_document_version(
        self, job_id: str, version: int
    ) -> dict[str, Any] | None: ...

    def save_evaluation(
        self,
        job_id: str,
        document_version: int | None,
        evaluation: dict[str, Any],
    ) -> None: ...
