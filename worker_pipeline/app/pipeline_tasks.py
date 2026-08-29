import hashlib
import logging
import time

import httpx

from app.celery_app import celery_app
from app.config import settings
from app.database import database_repository
from app.events import publish_event
from app.files import materialize_file, result_path, version_path
from app.models import JobStatus, TERMINAL_STATUSES
from app.pipeline_client import PipelineClient
from app.store import get_job, update_job
from app.supabase import supabase_repository


logger = logging.getLogger(__name__)

_UPSTREAM_STATUS = {
    "queued": JobStatus.RUNNING,
    "running": JobStatus.RUNNING,
    "done": JobStatus.DONE,
    "failed": JobStatus.FAILED,
    "blocked": JobStatus.BLOCKED,
    "security_blocked": JobStatus.SECURITY_BLOCKED,
}


def _retry_countdown(retry_number: int) -> int:
    intervals = settings.worker_retry_intervals_seconds
    return intervals[min(retry_number, len(intervals) - 1)]


def _rate_limit_delay(exc: httpx.HTTPStatusError, consecutive_429s: int) -> float:
    """Return a bounded delay for an upstream 429 without failing the job."""
    retry_after = exc.response.headers.get("Retry-After", "").strip()
    try:
        header_delay = max(0.0, float(retry_after)) if retry_after else 0.0
    except ValueError:
        header_delay = 0.0
    exponential_delay = settings.pipeline_rate_limit_backoff_seconds * min(
        2 ** max(0, consecutive_429s - 1), 8
    )
    return min(300.0, max(header_delay, exponential_delay))


def _update_stage_timings(record, new_stage: str | None, completed: list[str]) -> dict:
    timings = {key: dict(value) for key, value in (record.stage_timings or {}).items()}
    now = time.time()
    previous = record.current_stage
    if previous and previous != new_stage and previous in timings:
        timings[previous].setdefault("ended_at", now)
    if new_stage:
        timings.setdefault(new_stage, {"started_at": now})
    for stage in completed:
        if stage in timings:
            timings[stage].setdefault("ended_at", now)
    return timings


@celery_app.task(bind=True, name="pipeline.execute")
def execute_pipeline_job(self, job_id: str) -> str:
    record = get_job(job_id)
    if record is None:
        raise RuntimeError(f"Job {job_id} no longer exists")
    if record.status == JobStatus.CANCELLED:
        return job_id
    client = PipelineClient()
    try:
        upstream_run_id = record.upstream_run_id
        if not upstream_run_id:
            tender = materialize_file(
                record.tender_path, record.tender_object_key, record.tender_filename
            )
            template = None
            if record.template_filename:
                template = materialize_file(
                    record.template_path,
                    record.template_object_key,
                    record.template_filename,
                )
            update_job(job_id, status=JobStatus.SUBMITTING, error=None)
            upstream_run_id = client.submit(tender, template)
            update_job(
                job_id,
                status=JobStatus.RUNNING,
                upstream_run_id=upstream_run_id,
            )
            logger.info("Job %s mapped to pipeline run %s", job_id, upstream_run_id)

        deadline = time.monotonic() + settings.pipeline_max_poll_seconds
        consecutive_429s = 0
        while time.monotonic() < deadline:
            current = get_job(job_id)
            if current is None:
                raise RuntimeError(f"Job {job_id} disappeared while running")
            if current.status == JobStatus.CANCELLED:
                return job_id

            try:
                upstream = client.get_run(upstream_run_id)
                consecutive_429s = 0
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429:
                    raise
                consecutive_429s += 1
                delay = _rate_limit_delay(exc, consecutive_429s)
                remaining = max(0.0, deadline - time.monotonic())
                if remaining <= 0:
                    break
                delay = min(delay, remaining)
                logger.warning(
                    "Pipeline run %s polling was rate-limited; keeping job %s "
                    "running and retrying in %.1fs",
                    upstream_run_id,
                    job_id,
                    delay,
                )
                update_job(job_id, status=JobStatus.RUNNING, error=None)
                publish_event(
                    job_id,
                    "monitoring_delayed",
                    {
                        "reason": "upstream_rate_limited",
                        "retry_in_seconds": delay,
                        "upstream_run_id": upstream_run_id,
                    },
                )
                time.sleep(delay)
                continue
            upstream_status = _UPSTREAM_STATUS.get(
                str(upstream.get("run_status", "running")), JobStatus.RUNNING
            )
            completed = list(upstream.get("completed_stages") or [])
            stage = upstream.get("current_stage")
            timings = _update_stage_timings(current, stage, completed)
            next_status = (
                JobStatus.EVALUATING
                if upstream_status in TERMINAL_STATUSES
                else JobStatus.RUNNING
            )
            update_job(
                job_id,
                status=next_status,
                current_stage=stage,
                completed_stages=completed,
                progress=upstream.get("generation_progress"),
                upstream_state={
                    **(upstream.get("state") or {}),
                    "telemetry": upstream.get("telemetry") or {},
                },
                upstream_terminal_status=(
                    upstream_status.value
                    if upstream_status in TERMINAL_STATUSES
                    else None
                ),
                stage_timings=timings,
                error=upstream.get("error"),
            )
            if upstream_status in TERMINAL_STATUSES:
                publish_event(
                    job_id,
                    "pipeline_complete",
                    {
                        "upstream_run_id": upstream_run_id,
                        "upstream_status": upstream_status,
                    },
                )
                return job_id
            time.sleep(settings.pipeline_poll_interval_seconds)

        raise TimeoutError(
            f"Pipeline run {upstream_run_id} exceeded "
            f"{settings.pipeline_max_poll_seconds} seconds"
        )
    except (httpx.HTTPError, TimeoutError, ConnectionError) as exc:
        if self.request.retries < settings.worker_max_retries:
            countdown = _retry_countdown(self.request.retries)
            update_job(
                job_id,
                status=JobStatus.QUEUED,
                error=f"Transient failure; retrying in {countdown}s: {exc}",
            )
            raise self.retry(exc=exc, countdown=countdown)
        update_job(job_id, status=JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
        raise
    except Exception as exc:
        logger.exception("Worker job %s failed", job_id)
        update_job(job_id, status=JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        client.close()


@celery_app.task(name="pipeline.version_document")
def save_document_version(job_id: str) -> str:
    record = get_job(job_id)
    if record is None:
        raise RuntimeError(f"Unknown job {job_id}")
    if record.status == JobStatus.CANCELLED:
        return job_id
    draft = str((record.upstream_state or {}).get("draft_proposal") or "")
    if not draft:
        publish_event(
            job_id,
            "version_skipped",
            {"reason": "The pipeline did not produce a draft proposal."},
        )
        return job_id

    output = result_path(job_id)
    content = draft.encode("utf-8")
    if record.upstream_run_id:
        client = PipelineClient()
        try:
            try:
                content = client.download(record.upstream_run_id)
            except httpx.HTTPError:
                logger.warning("Using state draft because pipeline download failed")
        finally:
            client.close()
    output.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()

    repository = database_repository()
    storage = supabase_repository()
    version = (record.document_version or 0) + 1
    object_key: str | None = None
    try:
        if repository is not None:
            version = repository.next_document_version(job_id)
            local_version = version_path(job_id, version)
            local_version.write_bytes(content)
            object_key = str(local_version)
            if storage is not None:
                object_key = f"jobs/{job_id}/versions/v{version}/proposal.md"
                storage.upload_bytes(
                    object_key, content, "text/markdown; charset=utf-8"
                )
            repository.save_document_version(
                job_id, version, object_key, checksum, len(content)
            )
    finally:
        if repository is not None:
            repository.close()
        if storage is not None:
            storage.close()
    update_job(
        job_id,
        status=JobStatus.EVALUATING,
        current_stage="evaluation",
        result_path=str(output),
        result_object_key=object_key,
        document_version=version,
    )
    publish_event(
        job_id,
        "version_created",
        {"version": version, "object_key": object_key, "checksum": checksum},
    )
    return job_id
