from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    SUBMITTING = "submitting"
    RUNNING = "running"
    EVALUATING = "evaluating"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    SECURITY_BLOCKED = "security_blocked"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    JobStatus.DONE,
    JobStatus.FAILED,
    JobStatus.BLOCKED,
    JobStatus.SECURITY_BLOCKED,
    JobStatus.CANCELLED,
}


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    tender_filename: str
    template_filename: str | None = None
    tender_path: str | None = None
    template_path: str | None = None
    evaluation_path: str | None = None
    tender_object_key: str | None = None
    template_object_key: str | None = None
    evaluation_object_key: str | None = None
    created_at: float
    updated_at: float
    upstream_run_id: str | None = None
    celery_task_id: str | None = None
    current_stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    progress: dict[str, Any] | None = None
    result_path: str | None = None
    result_object_key: str | None = None
    document_version: int | None = None
    upstream_terminal_status: str | None = None
    upstream_state: dict[str, Any] | None = None
    stage_timings: dict[str, dict[str, float]] = Field(default_factory=dict)
    evaluation_results: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class JobSummary(BaseModel):
    job_id: str
    status: JobStatus
    tender_filename: str
    template_filename: str | None = None
    created_at: float
    updated_at: float
    upstream_run_id: str | None = None
    current_stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    progress: dict[str, Any] | None = None
    error: str | None = None
