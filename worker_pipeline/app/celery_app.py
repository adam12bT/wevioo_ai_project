from celery import Celery, Task

from app.config import settings


celery_app = Celery(
    "rfp_pipeline_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.pipeline_tasks", "app.evaluation.tasks"],
)
celery_app.conf.update(
    task_default_queue=settings.queue_name,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=settings.result_ttl_seconds,
    task_time_limit=settings.job_timeout_seconds,
    task_soft_time_limit=max(60, settings.job_timeout_seconds - 30),
    timezone="UTC",
    enable_utc=True,
)


class JobAwareTask(Task):
    """Ensure an unhandled task failure becomes visible through API and SSE."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = None
        if args and isinstance(args[0], str):
            job_id = args[0]
        elif args and isinstance(args[0], list) and args[0]:
            job_id = args[0][0].get("job_id")
        if job_id:
            from app.events import publish_event
            from app.models import JobStatus
            from app.store import update_job

            try:
                update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}",
                )
                publish_event(
                    job_id,
                    "failed",
                    {"job_id": job_id, "task_id": task_id, "error": str(exc)},
                )
            except Exception:
                pass
        super().on_failure(exc, task_id, args, kwargs, einfo)


celery_app.Task = JobAwareTask
