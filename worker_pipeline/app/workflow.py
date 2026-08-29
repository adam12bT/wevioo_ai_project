from celery import chain, group

from app.celery_app import celery_app
from app.evaluation.tasks import (
    aggregate_evaluations,
    evaluate_output,
    evaluate_performance,
    evaluate_rag,
)
from app.pipeline_tasks import execute_pipeline_job, save_document_version


def start_pipeline_workflow(job_id: str) -> str:
    workflow = chain(
        execute_pipeline_job.s(job_id),
        save_document_version.s(),
        group(
            evaluate_rag.s(),
            evaluate_output.s(),
            evaluate_performance.s(),
        ),
        aggregate_evaluations.s(),
    )
    result = workflow.apply_async()
    return str(result.id)


def revoke_pipeline_workflow(task_id: str) -> None:
    celery_app.control.revoke(task_id, terminate=False)

