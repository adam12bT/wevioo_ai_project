import logging
import time
from typing import Any

from app.config import settings
from app.database import database_repository
from app.models import JobRecord, JobSummary
from app.events import publish_event
from app.redis_client import redis_connection


_INDEX_KEY = "rfp-worker:jobs"
logger = logging.getLogger(__name__)


def _job_key(job_id: str) -> str:
    return f"rfp-worker:job:{job_id}"


def save_job(
    record: JobRecord,
    *,
    emit: bool = True,
    strict_database: bool = False,
) -> JobRecord:
    record.updated_at = time.time()
    redis = redis_connection()
    pipeline = redis.pipeline()
    pipeline.setex(
        _job_key(record.job_id),
        settings.job_ttl_seconds,
        record.model_dump_json(),
    )
    pipeline.zadd(_INDEX_KEY, {record.job_id: record.created_at})
    pipeline.execute()
    repository = None
    try:
        repository = database_repository()
    except Exception:
        logger.exception("Could not connect to the durable database")
        if strict_database:
            raise
    if repository is not None:
        try:
            repository.upsert_job(record)
        except Exception:
            logger.exception("Could not mirror job %s to the database", record.job_id)
            if strict_database:
                raise
        finally:
            repository.close()
    if emit:
        publish_event(
            record.job_id,
            "progress",
            {
                "job_id": record.job_id,
                "status": record.status,
                "current_stage": record.current_stage,
                "completed_stages": record.completed_stages,
                "progress": record.progress,
                "document_version": record.document_version,
                "error": record.error,
                "updated_at": record.updated_at,
            },
        )
    return record


def get_job(job_id: str) -> JobRecord | None:
    raw = redis_connection().get(_job_key(job_id))
    if raw is None:
        repository = None
        try:
            repository = database_repository()
        except Exception:
            logger.exception("Could not connect to the durable database")
        if repository is None:
            return None
        try:
            record = repository.get_job(job_id)
        except Exception:
            logger.exception("Could not restore job %s from the database", job_id)
            return None
        finally:
            repository.close()
        if record is not None:
            save_job(record, emit=False)
        return record
    return JobRecord.model_validate_json(raw)


def update_job(job_id: str, **changes: Any) -> JobRecord:
    record = get_job(job_id)
    if record is None:
        raise KeyError(f"Unknown job: {job_id}")
    updated = record.model_copy(update=changes)
    return save_job(updated)


def list_jobs(limit: int = 50) -> list[JobSummary]:
    redis = redis_connection()
    job_ids = redis.zrevrange(_INDEX_KEY, 0, max(0, limit - 1))
    records: list[JobSummary] = []
    stale: list[bytes] = []
    for raw_id in job_ids:
        job_id = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
        record = get_job(job_id)
        if record is None:
            stale.append(raw_id)
            continue
        records.append(JobSummary(**record.model_dump()))
    if stale:
        redis.zrem(_INDEX_KEY, *stale)
    if not records:
        repository = None
        try:
            repository = database_repository()
        except Exception:
            logger.exception("Could not connect to the durable database")
        if repository is not None:
            try:
                records = [
                    JobSummary(**record.model_dump())
                    for record in repository.list_jobs(limit)
                ]
            except Exception:
                logger.exception("Could not list jobs from the database")
            finally:
                repository.close()
    return records


def redis_is_ready() -> bool:
    return bool(redis_connection().ping())
