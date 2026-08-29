-- Run this once in Supabase SQL Editor. All tables remain private; the worker
-- accesses them only through SUPABASE_SERVICE_ROLE_KEY.

create table if not exists public.worker_jobs (
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

alter table public.worker_jobs add column if not exists tender_path text;
alter table public.worker_jobs add column if not exists template_path text;
alter table public.worker_jobs add column if not exists evaluation_path text;
alter table public.worker_jobs add column if not exists result_path text;
alter table public.worker_jobs alter column template_filename drop not null;

create table if not exists public.document_versions (
  id bigint generated always as identity primary key,
  job_id text not null references public.worker_jobs(job_id) on delete cascade,
  version integer not null,
  object_key text not null,
  checksum_sha256 text not null,
  size_bytes bigint not null,
  created_at timestamptz not null default now(),
  unique (job_id, version)
);

create table if not exists public.evaluation_reports (
  id bigint generated always as identity primary key,
  job_id text not null references public.worker_jobs(job_id) on delete cascade,
  document_version integer not null default 0,
  report jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (job_id, document_version)
);

alter table public.worker_jobs enable row level security;
alter table public.document_versions enable row level security;
alter table public.evaluation_reports enable row level security;

insert into storage.buckets (id, name, public, file_size_limit)
values ('rfp-files', 'rfp-files', false, 52428800)
on conflict (id) do update set public = false, file_size_limit = 52428800;
