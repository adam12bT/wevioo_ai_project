from app.celery_app import celery_app
from app.database import database_repository
from app.events import publish_event
from app.files import materialize_file
from app.models import JobStatus
from app.store import get_job, update_job

from .output import evaluate_output as calculate_output_metrics
from .performance import evaluate_performance as calculate_performance_metrics
from .rag import evaluate_rag as calculate_rag_metrics, load_dataset


@celery_app.task(name="evaluation.rag")
def evaluate_rag(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise RuntimeError(f"Unknown job {job_id}")
    try:
        dataset_path = None
        if record.evaluation_path or record.evaluation_object_key:
            dataset_path = materialize_file(
                record.evaluation_path,
                record.evaluation_object_key,
                f"evaluation-{job_id}.json",
            )
        result = calculate_rag_metrics(
            record.upstream_state or {}, load_dataset(dataset_path), k=5
        )
    except Exception as exc:
        result = {
            "available": False,
            "reason": f"RAG evaluation failed: {type(exc).__name__}: {exc}",
            "precision_at_k": None,
            "recall_at_k": None,
            "mrr": None,
            "case_count": 0,
        }
    publish_event(job_id, "evaluation", {"dimension": "rag", "result": result})
    return {"job_id": job_id, "dimension": "rag", "result": result}


@celery_app.task(name="evaluation.output")
def evaluate_output(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise RuntimeError(f"Unknown job {job_id}")
    result = calculate_output_metrics(record.upstream_state or {})
    publish_event(job_id, "evaluation", {"dimension": "output", "result": result})
    return {"job_id": job_id, "dimension": "output", "result": result}


@celery_app.task(name="evaluation.performance")
def evaluate_performance(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise RuntimeError(f"Unknown job {job_id}")
    result = calculate_performance_metrics(record)
    publish_event(
        job_id, "evaluation", {"dimension": "performance", "result": result}
    )
    return {"job_id": job_id, "dimension": "performance", "result": result}


@celery_app.task(name="evaluation.aggregate")
def aggregate_evaluations(results: list[dict]) -> dict:
    if not results:
        raise RuntimeError("Evaluation chord returned no results")
    job_id = str(results[0]["job_id"])
    report = {
        str(item["dimension"]): item["result"]
        for item in results
        if item.get("dimension")
    }
    record = get_job(job_id)
    if record is None:
        raise RuntimeError(f"Unknown job {job_id}")
    final_status = (
        JobStatus.CANCELLED
        if record.status == JobStatus.CANCELLED
        else JobStatus(record.upstream_terminal_status or JobStatus.DONE)
    )
    updated = update_job(
        job_id,
        status=final_status,
        current_stage="evaluation_complete",
        evaluation_results=report,
    )
    repository = database_repository()
    if repository is not None:
        try:
            repository.save_evaluation(job_id, record.document_version, report)
        finally:
            repository.close()
    publish_event(
        job_id,
        "complete",
        {"job_id": job_id, "status": updated.status, "evaluation": report},
    )
    return {"job_id": job_id, "status": updated.status, "evaluation": report}
