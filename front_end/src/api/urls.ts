// Centralized API URLs. Single source of truth — components never build URLs themselves.

const WORKER_ROOT = (import.meta.env.VITE_WORKER_API_URL || '').replace(/\/+$/, '');
const WORKER_API_URL = WORKER_ROOT.endsWith('/api') ? WORKER_ROOT : `${WORKER_ROOT}/api`;
const AGENT_ROOT = (import.meta.env.VITE_AGENT_API_BASE_URL || '').replace(/\/+$/, '');
const AGENT_API_BASE_URL = AGENT_ROOT.endsWith('/api') ? AGENT_ROOT : `${AGENT_ROOT}/api`;
const EXTRACTOR_ROOT = (import.meta.env.VITE_EXTRACTOR_API_URL || '').replace(/\/+$/, '');
const ANYTHINGLLM_ROOT = (import.meta.env.VITE_ANYTHINGLLM_API_URL || '').replace(/\/+$/, '');

function serviceOrigin(url: string): string {
  return url.replace(/\/api$/i, '');
}

export const SPACE_WAKE_URLS = Array.from(
  new Set(
    [WORKER_ROOT, serviceOrigin(AGENT_ROOT), EXTRACTOR_ROOT, serviceOrigin(ANYTHINGLLM_ROOT)]
      .filter(Boolean),
  ),
);

if (!WORKER_API_URL || !AGENT_API_BASE_URL) {
  console.warn('[api] Missing VITE_WORKER_API_URL or VITE_AGENT_API_BASE_URL environment variables.');
}

export const API = {
  worker: WORKER_API_URL,
  agent: AGENT_API_BASE_URL,
  extractor: EXTRACTOR_ROOT,
  anythingllm: ANYTHINGLLM_ROOT,
  // Worker — jobs
  jobs: () => `${WORKER_API_URL}/jobs`,
  job: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}`,
  jobEvents: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}/events`,
  cancelJob: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}/cancel`,
  rerunJob: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}/rerun`,
  jobEvaluation: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}/evaluation`,
  jobVersions: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}/versions`,
  jobDownload: (jobId: string) => `${WORKER_API_URL}/jobs/${jobId}/download`,
  versionDownload: (jobId: string, version: string | number) =>
    `${WORKER_API_URL}/jobs/${jobId}/versions/${version}/download`,
  // Worker — health
  health: () => `${WORKER_ROOT}/health`,
  extractorHealth: () => (EXTRACTOR_ROOT ? `${EXTRACTOR_ROOT}/health` : ''),
};

export type ApiUrls = typeof API;
