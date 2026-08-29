from __future__ import annotations

from threading import Lock
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings
from app.models import JobRecord


_SCHEMA = """
create table if not exists worker_jobs (
  job_id text primary key,
  status text not null,
  tender_filename text not null,
  template_filename text,
  tender_path text,
  template_path text,
  evaluation_path text,
  upstream_run_id text,
  celery_task_id text,
  current_stage text,
  completed_stages jsonb not null default '[]'::jsonb,
  progress jsonb,
  tender_object_key text,
  template_object_key text,
  evaluation_object_key text,
  result_object_key text,
  result_path text,
  document_version integer,
  upstream_terminal_status text,
  stage_timings jsonb not null default '{}'::jsonb,
  evaluation_results jsonb not null default '{}'::jsonb,
  upstream_state jsonb,
  error text,
  created_at_epoch double precision not null,
  updated_at_epoch double precision not null
);

create table if not exists document_versions (
  id bigint generated always as identity primary key,
  job_id text not null references worker_jobs(job_id) on delete cascade,
  version integer not null,
  object_key text not null,
  checksum_sha256 text not null,
  size_bytes bigint not null,
  created_at timestamptz not null default now(),
  unique (job_id, version)
);

create table if not exists evaluation_reports (
  id bigint generated always as identity primary key,
  job_id text not null references worker_jobs(job_id) on delete cascade,
  document_version integer not null default 0,
  report jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (job_id, document_version)
);

alter table worker_jobs add column if not exists tender_path text;
alter table worker_jobs add column if not exists template_path text;
alter table worker_jobs add column if not exists evaluation_path text;
alter table worker_jobs add column if not exists result_path text;
alter table worker_jobs alter column template_filename drop not null;
"""

_schema_lock = Lock()
_schema_initialized = False


class PostgresRepository:
    """Durable repository for a standard PostgreSQL database."""

    def __init__(self) -> None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        self._connection = psycopg.connect(
            settings.database_url, row_factory=dict_row, autocommit=True
        )
        if settings.database_auto_create:
            self._initialize_schema_once()

    def _initialize_schema_once(self) -> None:
        global _schema_initialized
        if _schema_initialized:
            return
        with _schema_lock:
            if _schema_initialized:
                return
            with self._connection.cursor() as cursor:
                cursor.execute(_SCHEMA)
            _schema_initialized = True

    def close(self) -> None:
        self._connection.close()

    def health(self) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute("select 1 as ready")
            return cursor.fetchone()["ready"] == 1

    @staticmethod
    def _record(row: dict[str, Any]) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"], status=row["status"],
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
            upstream_state=row.get("upstream_state"), error=row.get("error"),
        )

    def upsert_job(self, record: JobRecord) -> None:
        values = (
            record.job_id, record.status.value, record.tender_filename,
            record.template_filename, record.tender_path, record.template_path,
            record.evaluation_path, record.upstream_run_id,
            record.celery_task_id, record.current_stage,
            Jsonb(record.completed_stages),
            Jsonb(record.progress) if record.progress is not None else None,
            record.tender_object_key, record.template_object_key,
            record.evaluation_object_key, record.result_object_key,
            record.result_path,
            record.document_version, record.upstream_terminal_status,
            Jsonb(record.stage_timings), Jsonb(record.evaluation_results),
            Jsonb(record.upstream_state) if record.upstream_state is not None else None,
            record.error, record.created_at, record.updated_at,
        )
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                insert into worker_jobs (
                  job_id, status, tender_filename, template_filename,
                  tender_path, template_path, evaluation_path,
                  upstream_run_id, celery_task_id, current_stage,
                  completed_stages, progress, tender_object_key,
                  template_object_key, evaluation_object_key, result_object_key,
                  result_path,
                  document_version, upstream_terminal_status, stage_timings,
                  evaluation_results, upstream_state, error, created_at_epoch,
                  updated_at_epoch
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                on conflict (job_id) do update set
                  status=excluded.status, upstream_run_id=excluded.upstream_run_id,
                  tender_path=excluded.tender_path,
                  template_path=excluded.template_path,
                  evaluation_path=excluded.evaluation_path,
                  celery_task_id=excluded.celery_task_id,
                  current_stage=excluded.current_stage,
                  completed_stages=excluded.completed_stages,
                  progress=excluded.progress,
                  tender_object_key=excluded.tender_object_key,
                  template_object_key=excluded.template_object_key,
                  evaluation_object_key=excluded.evaluation_object_key,
                  result_object_key=excluded.result_object_key,
                  result_path=excluded.result_path,
                  document_version=excluded.document_version,
                  upstream_terminal_status=excluded.upstream_terminal_status,
                  stage_timings=excluded.stage_timings,
                  evaluation_results=excluded.evaluation_results,
                  upstream_state=excluded.upstream_state, error=excluded.error,
                  updated_at_epoch=excluded.updated_at_epoch
                """,
                values,
            )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connection.cursor() as cursor:
            cursor.execute("select * from worker_jobs where job_id=%s", (job_id,))
            row = cursor.fetchone()
        return self._record(row) if row else None

    def list_jobs(self, limit: int) -> list[JobRecord]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "select * from worker_jobs order by created_at_epoch desc limit %s",
                (limit,),
            )
            return [self._record(row) for row in cursor.fetchall()]

    def next_document_version(self, job_id: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "select coalesce(max(version),0)+1 as version "
                "from document_versions where job_id=%s", (job_id,)
            )
            return int(cursor.fetchone()["version"])

    def save_document_version(
        self, job_id: str, version: int, object_key: str,
        checksum: str, size_bytes: int,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                insert into document_versions
                  (job_id,version,object_key,checksum_sha256,size_bytes)
                values (%s,%s,%s,%s,%s)
                on conflict (job_id,version) do update set
                  object_key=excluded.object_key,
                  checksum_sha256=excluded.checksum_sha256,
                  size_bytes=excluded.size_bytes
                """, (job_id, version, object_key, checksum, size_bytes)
            )

    def list_document_versions(self, job_id: str) -> list[dict[str, Any]]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """select version,object_key,checksum_sha256,size_bytes,created_at
                   from document_versions where job_id=%s order by version desc""",
                (job_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_document_version(
        self, job_id: str, version: int
    ) -> dict[str, Any] | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """select version,object_key,checksum_sha256,size_bytes,created_at
                   from document_versions where job_id=%s and version=%s""",
                (job_id, version),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    def save_evaluation(
        self, job_id: str, document_version: int | None,
        evaluation: dict[str, Any],
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                insert into evaluation_reports (job_id,document_version,report)
                values (%s,%s,%s)
                on conflict (job_id,document_version) do update set
                  report=excluded.report, updated_at=now()
                """, (job_id, document_version or 0, Jsonb(evaluation))
            )
