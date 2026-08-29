import asyncio
import json
import logging
from pathlib import Path
from threading import Lock
import time
import uuid

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.config import settings
from app.database import database_repository
from app.events import read_events
from app.files import (
    prepare_storage,
    safe_filename,
    save_upload,
    upload_durable,
    validate_extension,
)
from app.logging_config import configure_logging
from app.models import JobRecord, JobStatus, JobSummary, TERMINAL_STATUSES
from app.pipeline_client import PipelineClient
from app.store import get_job, list_jobs, redis_is_ready, save_job, update_job
from app.supabase import supabase_repository
from app.workflow import revoke_pipeline_workflow, start_pipeline_workflow


configure_logging()
logger = logging.getLogger(__name__)

_pipeline_health_lock = Lock()
_pipeline_health_checked_at = 0.0
_pipeline_health_ready = False
_pipeline_health_error: str | None = None

app = FastAPI(
    title="RFP Pipeline Worker API",
    version="0.3.0",
    description="Celery/Redis worker, SSE progress, versioning and evaluation API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


@app.on_event("startup")
def startup() -> None:
    prepare_storage()


def _cached_pipeline_health() -> tuple[bool, str | None]:
    """Avoid turning every frontend health refresh into an agent API request."""
    global _pipeline_health_checked_at
    global _pipeline_health_ready
    global _pipeline_health_error

    now = time.monotonic()
    with _pipeline_health_lock:
        if now - _pipeline_health_checked_at < settings.pipeline_health_cache_seconds:
            return _pipeline_health_ready, _pipeline_health_error

        client = PipelineClient()
        try:
            _pipeline_health_ready = bool(client.health().get("ok"))
            _pipeline_health_error = None
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 429 and _pipeline_health_checked_at > 0:
                logger.warning(
                    "Agent health check was rate-limited; reusing the last cached state"
                )
                _pipeline_health_error = None
            else:
                _pipeline_health_ready = False
                _pipeline_health_error = str(exc)
        finally:
            client.close()
            _pipeline_health_checked_at = now
        return _pipeline_health_ready, _pipeline_health_error


@app.get("/health")
def health() -> dict:
    redis_ready = False
    pipeline_ready = False
    database_ready = not settings.database_required
    storage_ready = not settings.supabase_required
    errors: dict[str, str] = {}
    try:
        redis_ready = redis_is_ready()
    except Exception as exc:
        errors["redis"] = str(exc)
    pipeline_ready, pipeline_error = _cached_pipeline_health()
    if pipeline_error:
        errors["pipeline"] = pipeline_error
    repository = None
    try:
        repository = database_repository()
        if repository is not None:
            database_ready = repository.health()
        elif settings.database_required:
            errors["database"] = "The configured database provider is unavailable"
    except Exception as exc:
        errors["database"] = str(exc)
    finally:
        if repository is not None:
            repository.close()
    if settings.supabase_enabled:
        storage_ready = True
    elif settings.supabase_required:
        errors["storage"] = "Supabase Storage is required but not configured"
    return {
        "ok": redis_ready and pipeline_ready and database_ready and storage_ready,
        "redis": redis_ready,
        "pipeline": pipeline_ready,
        "database": {
            "provider": settings.database_provider,
            "ready": database_ready,
        },
        "object_storage": {
            "provider": "supabase" if settings.supabase_enabled else "local",
            "ready": storage_ready,
        },
        "celery_queue": settings.queue_name,
        "errors": errors,
    }


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    template: UploadFile | None = File(default=None),
    evaluation_dataset: UploadFile | None = File(default=None),
) -> dict:
    tender_name = safe_filename(file.filename, "tender.pdf")
    template_name = safe_filename(template.filename, "template.docx") if template else None
    try:
        validate_extension(tender_name)
        if template_name:
            validate_extension(template_name)
        if (
            evaluation_dataset
            and Path(evaluation_dataset.filename or "").suffix.lower() != ".json"
        ):
            raise ValueError("The optional evaluation_dataset must be a JSON file")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = uuid.uuid4().hex[:12]
    tender_path = save_upload(job_id, "tender", tender_name, file.file)
    template_path = (
        save_upload(job_id, "template", template_name, template.file)
        if template and template_name
        else None
    )
    evaluation_path = None
    if evaluation_dataset:
        evaluation_path = save_upload(
            job_id,
            "evaluation",
            safe_filename(evaluation_dataset.filename, "evaluation.json"),
            evaluation_dataset.file,
        )
    try:
        tender_key = upload_durable(job_id, "inputs", tender_path)
        template_key = upload_durable(job_id, "inputs", template_path) if template_path else None
        evaluation_key = (
            upload_durable(job_id, "evaluation", evaluation_path, "application/json")
            if evaluation_path
            else None
        )
        if settings.supabase_required and (
            not tender_key or (template_path is not None and not template_key)
        ):
            raise RuntimeError("Supabase persistence is required but unavailable")
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not persist uploaded documents: {exc}"
        ) from exc

    now = time.time()
    record = JobRecord(
        job_id=job_id,
        tender_filename=tender_name,
        template_filename=template_name,
        tender_path=str(tender_path),
        template_path=str(template_path) if template_path else None,
        evaluation_path=str(evaluation_path) if evaluation_path else None,
        tender_object_key=tender_key,
        template_object_key=template_key,
        evaluation_object_key=evaluation_key,
        created_at=now,
        updated_at=now,
    )
    try:
        save_job(record, strict_database=settings.database_required)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not persist the job record in the database: {exc}",
        ) from exc
    try:
        task_id = start_pipeline_workflow(job_id)
        update_job(job_id, celery_task_id=task_id)
    except Exception as exc:
        update_job(job_id, status=JobStatus.FAILED, error=f"Queue error: {exc}")
        raise HTTPException(status_code=503, detail="Could not enqueue job") from exc
    return {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "events_url": f"/api/jobs/{job_id}/events",
    }


@app.get("/api/jobs", response_model=list[JobSummary])
def get_jobs(limit: int = Query(default=50, ge=1, le=200)) -> list[JobSummary]:
    return list_jobs(limit)


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str) -> JobRecord:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return record


@app.get("/api/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def generate():
        cursor = last_event_id or "0-0"
        while True:
            events = await asyncio.to_thread(read_events, job_id, cursor, 15000)
            if not events:
                yield ": heartbeat\n\n"
                record = get_job(job_id)
                if record and record.status in TERMINAL_STATUSES:
                    break
                continue
            for event in events:
                cursor = event["id"]
                payload = json.dumps(event["data"], ensure_ascii=False, default=str)
                yield f"id: {cursor}\nevent: {event['event']}\ndata: {payload}\n\n"
                if event["event"] == "complete":
                    return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status in TERMINAL_STATUSES:
        return {"job_id": job_id, "status": record.status}
    update_job(job_id, status=JobStatus.CANCELLED)
    if record.celery_task_id:
        revoke_pipeline_workflow(record.celery_task_id)
    return {"job_id": job_id, "status": JobStatus.CANCELLED}


@app.post("/api/jobs/{job_id}/rerun")
def rerun_job(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status not in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="The current run is still active")
    update_job(
        job_id,
        status=JobStatus.QUEUED,
        upstream_run_id=None,
        celery_task_id=None,
        current_stage=None,
        completed_stages=[],
        progress=None,
        upstream_terminal_status=None,
        upstream_state=None,
        stage_timings={},
        evaluation_results={},
        error=None,
    )
    try:
        task_id = start_pipeline_workflow(job_id)
        update_job(job_id, celery_task_id=task_id)
    except Exception as exc:
        update_job(job_id, status=JobStatus.FAILED, error=f"Queue error: {exc}")
        raise HTTPException(status_code=503, detail="Could not enqueue rerun") from exc
    return {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "next_version": (record.document_version or 0) + 1,
    }


@app.get("/api/jobs/{job_id}/evaluation")
def get_evaluation(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not record.evaluation_results:
        raise HTTPException(status_code=409, detail="Evaluation is not available")
    return record.evaluation_results


@app.get("/api/jobs/{job_id}/versions")
def get_document_versions(job_id: str) -> list[dict]:
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    repository = database_repository()
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail="Persistent document version history requires a database",
        )
    try:
        return repository.list_document_versions(job_id)
    finally:
        repository.close()


@app.get(
    "/api/jobs/{job_id}/versions/{version}/download",
)
def download_document_version(job_id: str, version: int) -> Response:
    if version < 1:
        raise HTTPException(status_code=400, detail="Version must be at least 1")
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    repository = database_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    try:
        item = repository.get_document_version(job_id, version)
        if item is None:
            raise HTTPException(status_code=404, detail="Document version not found")
    finally:
        repository.close()
    object_key = str(item["object_key"])
    local_version = Path(object_key)
    if local_version.is_file():
        return FileResponse(
            local_version,
            media_type="text/markdown",
            filename=f"proposal-{job_id}-v{version}.md",
        )
    storage = supabase_repository()
    if storage is None:
        raise HTTPException(status_code=503, detail="Document storage is unavailable")
    try:
        content = storage.download_bytes(object_key)
    finally:
        storage.close()
    return Response(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                f'attachment; filename="proposal-{job_id}-v{version}.md"'
            )
        },
    )


@app.get("/api/jobs/{job_id}/download")
def download_result(job_id: str) -> Response:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.result_path and Path(record.result_path).is_file():
        return FileResponse(
            record.result_path,
            media_type="text/markdown",
            filename=f"proposal-{job_id}-v{record.document_version or 1}.md",
        )
    if record.result_object_key:
        repository = supabase_repository()
        if repository is None:
            raise HTTPException(status_code=503, detail="Supabase is unavailable")
        try:
            content = repository.download_bytes(record.result_object_key)
        finally:
            repository.close()
        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="proposal-{job_id}-'
                    f'v{record.document_version or 1}.md"'
                )
            },
        )
    raise HTTPException(status_code=409, detail="Result is not available")
