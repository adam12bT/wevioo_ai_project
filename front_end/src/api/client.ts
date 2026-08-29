// API client: thin wrappers around fetch for the worker + agent backends.
// All URL construction lives in urls.ts; all shape normalization lives in normalize.ts.

import { API } from './urls';
import {
  normalizeGenerationProgress,
  normalizeJob,
  normalizeJobsList,
} from './normalize';
import type {
  DocumentVersion,
  Evaluation,
  HealthResponse,
  Job,
  JobsListResponse,
} from '@/types';

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data.detail || data.message || data.error || JSON.stringify(data);
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = res.statusText;
      }
    }
    throw new ApiError(detail || res.statusText, res.status);
  }
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json() as Promise<T>;
  }
  return (await res.text()) as unknown as T;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err) {
    if (err instanceof TypeError) {
      throw new ApiError(
        'Network error — the service may be unavailable or blocking the request (CORS).',
      );
    }
    throw err;
  }
  return parseResponse<T>(res);
}

// ---------- Jobs ----------

export async function fetchJobs(): Promise<Job[]> {
  const data = await fetchJson<JobsListResponse | Job[]>(API.jobs());
  return normalizeJobsList(data);
}

export async function fetchJob(jobId: string): Promise<Job> {
  const data = await fetchJson<Job>(API.job(jobId));
  return normalizeJob(data);
}

export async function createJob(files: {
  file: File;
  template?: File | null;
  evaluation_dataset?: File | null;
}): Promise<Job> {
  const form = new FormData();
  form.append('file', files.file);
  if (files.template) {
    form.append('template', files.template);
  }
  if (files.evaluation_dataset) {
    form.append('evaluation_dataset', files.evaluation_dataset);
  }
  // Intentionally do NOT set Content-Type — browser sets multipart boundary.
  const data = await fetchJson<Job>(API.jobs(), { method: 'POST', body: form });
  return normalizeJob(data);
}

export async function cancelJob(jobId: string): Promise<Job> {
  const data = await fetchJson<Job>(API.cancelJob(jobId), { method: 'POST' });
  return normalizeJob(data);
}

export async function rerunJob(jobId: string): Promise<Job> {
  const data = await fetchJson<Job>(API.rerunJob(jobId), { method: 'POST' });
  return normalizeJob(data);
}

export async function fetchEvaluation(jobId: string): Promise<Evaluation> {
  const data = await fetchJson<Evaluation | { evaluation: Evaluation }>(API.jobEvaluation(jobId));
  const raw = data && (data as { evaluation?: Evaluation }).evaluation
    ? (data as { evaluation: Evaluation }).evaluation
    : (data as Evaluation);
  return normalizeJob({ evaluation_results: raw }).evaluation || {};
}

export async function fetchVersions(jobId: string): Promise<DocumentVersion[]> {
  const data = await fetchJson<DocumentVersion[] | { versions: DocumentVersion[] }>(
    API.jobVersions(jobId),
  );
  if (Array.isArray(data)) return data;
  return data.versions || [];
}

export async function downloadProposal(jobId: string): Promise<Blob> {
  const res = await fetch(API.jobDownload(jobId));
  if (!res.ok) {
    throw new ApiError('Download unavailable', res.status);
  }
  return res.blob();
}

export async function downloadVersion(jobId: string, version: string | number): Promise<Blob> {
  const res = await fetch(API.versionDownload(jobId, version));
  if (!res.ok) {
    throw new ApiError('Version download unavailable', res.status);
  }
  return res.blob();
}

export async function downloadBlob(blob: Blob, filename: string): Promise<void> {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------- Health ----------

export async function fetchHealth(): Promise<HealthResponse> {
  const raw = await fetchJson<Record<string, unknown>>(API.health());
  const database = (raw.database || {}) as Record<string, unknown>;
  const storage = (raw.object_storage || {}) as Record<string, unknown>;
  const errors = (raw.errors || {}) as Record<string, string>;
  const component = (ready: boolean, provider?: string): HealthResponse['redis'] => ({
    status: ready ? 'healthy' : 'unhealthy',
    ready,
    provider,
  });

  let extractor: HealthResponse['extractor'];
  if (!API.extractor) {
    extractor = {
      status: 'unknown',
      ready: false,
      configured: false,
      message: 'Set VITE_EXTRACTOR_API_URL to monitor this service.',
    };
  } else {
    try {
      const extractorRaw = await fetchJson<Record<string, unknown>>(API.extractorHealth(), {
        cache: 'no-store',
      });
      const extractorStatus = String(extractorRaw.status || '').toLowerCase();
      const extractorReady = extractorRaw.ok === true
        || extractorRaw.ready === true
        || ['ok', 'healthy', 'ready'].includes(extractorStatus);
      extractor = {
        status: extractorReady ? 'healthy' : 'unhealthy',
        ready: extractorReady,
        configured: true,
        provider: 'document extractor',
        endpoint: API.extractorHealth(),
        message: typeof extractorRaw.message === 'string' ? extractorRaw.message : undefined,
      };
    } catch (err) {
      extractor = {
        status: 'unhealthy',
        ready: false,
        configured: true,
        provider: 'document extractor',
        endpoint: API.extractorHealth(),
        message: err instanceof Error ? err.message : 'Extractor health request failed.',
      };
    }
  }

  const workerReady = raw.ok === true;
  const overallReady = workerReady && (extractor.configured !== true || extractor.ready === true);
  return {
    status: overallReady ? 'healthy' : 'unhealthy',
    redis: component(raw.redis === true),
    celery_queue: component(raw.redis === true, String(raw.celery_queue || 'unknown')),
    agent_pipeline: component(raw.pipeline === true),
    extractor,
    database: component(database.ready === true, String(database.provider || 'unknown')),
    storage: component(storage.ready === true, String(storage.provider || 'unknown')),
    errors,
  };
}

// ---------- Knowledge base (agent API) ----------

export interface KnowledgeUploadResult {
  id?: string;
  name?: string;
  status?: string;
  message?: string;
}

export async function uploadKnowledgeDocument(
  category: string,
  file: File,
): Promise<KnowledgeUploadResult> {
  const form = new FormData();
  form.append('file', file);
  return fetchJson<KnowledgeUploadResult>(`${API.agent}/knowledge/${category}/upload`, {
    method: 'POST',
    body: form,
  });
}

export async function fetchKnowledgeDocuments(): Promise<
  { id: string; name: string; category: string; size?: number; created_at?: string; status?: string }[]
> {
  const data = await fetchJson<Record<string, {
    documents?: { id?: string; title?: string; filename?: string }[];
  }>>(`${API.agent}/knowledge`);
  return Object.entries(data).flatMap(([category, workspace]) =>
    (workspace.documents || []).map((document, index) => ({
      id: String(document.id || `${category}-${index}`),
      name: document.title || document.filename || 'Unknown document',
      category,
      status: 'indexed',
    })),
  );
}

// Re-export normalization helpers for convenience
export { normalizeGenerationProgress, normalizeJob, normalizeJobsList };
