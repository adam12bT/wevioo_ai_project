// Normalization layer: turns the variety of backend shapes into a single, stable Job structure.
// This is the only place that knows about the different possible nesting of progress/generation.

import type {
  GenerationProgress,
  Job,
  JobStatus,
  PipelineStage,
  StageStatus,
} from '@/types';

/**
 * Extract generation progress regardless of where the backend stored it.
 * Priority: upstream_state.generation_progress > progress.generation > progress > null
 */
export function normalizeGenerationProgress(job: Job): GenerationProgress | null {
  const upstream = job.upstream_state?.generation_progress;
  if (upstream && typeof upstream === 'object' && 'sections' in upstream) {
    return upstream as GenerationProgress;
  }

  const nested = (job.progress as { generation?: GenerationProgress })?.generation;
  if (nested && typeof nested === 'object') {
    return nested;
  }

  // progress may itself be the generation progress object
  if (
    job.progress &&
    typeof job.progress === 'object' &&
    ('sections' in job.progress ||
      'overall_percent' in job.progress ||
      'current_section' in job.progress)
  ) {
    return job.progress as GenerationProgress;
  }

  return null;
}

const PIPELINE_STAGE_NAMES = [
  'verification',
  'document_processing',
  'extraction',
  'research',
  'generation',
  'security',
  'quality',
  'versioning',
  'evaluation',
  'completed',
] as const;

export const PIPELINE_STAGES: { key: string; label: string }[] = [
  { key: 'verification', label: 'Verification' },
  { key: 'document_processing', label: 'Document Processing' },
  { key: 'extraction', label: 'Extraction' },
  { key: 'research', label: 'Research' },
  { key: 'generation', label: 'Generation' },
  { key: 'security', label: 'Security' },
  { key: 'quality', label: 'Quality' },
  { key: 'versioning', label: 'Versioning' },
  { key: 'evaluation', label: 'Evaluation' },
  { key: 'completed', label: 'Completed' },
];

export function stageLabel(key: string): string {
  return PIPELINE_STAGES.find((s) => s.key === key)?.label || key;
}

export function normalizeStatus(raw: unknown): JobStatus {
  if (typeof raw === 'string') {
    const value = raw.toLowerCase();
    if (value === 'done') return 'completed';
    if (value === 'security_blocked') return 'blocked';
    const s = value as JobStatus;
    if (
      ['queued', 'submitting', 'running', 'evaluating', 'completed', 'failed', 'blocked', 'cancelled'].includes(s)
    ) {
      return s;
    }
  }
  return 'queued';
}

/**
 * Build a stages array with a status per stage based on current_stage / pipeline.
 */
export function normalizePipelineStages(job: Job): PipelineStage[] {
  const stageAliases: Record<string, string> = {
    verifier: 'verification',
    processing: 'document_processing',
    evaluation_complete: 'completed',
  };
  const rawCurrent = (job.current_stage || job.stage || job.pipeline?.current_stage || '').toLowerCase();
  const current = stageAliases[rawCurrent] || rawCurrent;
  const provided = job.pipeline?.stages;
  if (provided && Array.isArray(provided) && provided.length > 0) {
    return provided;
  }

  const completed = new Set(
    (job.completed_stages || []).map((stage) => stageAliases[stage] || stage),
  );
  const currentIdx = PIPELINE_STAGE_NAMES.indexOf(current as (typeof PIPELINE_STAGE_NAMES)[number]);
  return PIPELINE_STAGES.map((s, idx) => {
    let status: StageStatus = 'waiting';
    if (completed.has(s.key)) status = 'completed';
    if (job.status === 'completed') {
      status = 'completed';
    } else if (job.status === 'evaluating') {
      const evaluationIdx = PIPELINE_STAGE_NAMES.indexOf('evaluation');
      if (idx < evaluationIdx) status = 'completed';
      else if (idx === evaluationIdx) status = 'active';
    } else if (job.status === 'failed') {
      if (currentIdx >= 0) {
        if (idx < currentIdx) status = 'completed';
        else if (idx === currentIdx) status = 'failed';
      }
    } else if (job.status === 'blocked') {
      if (currentIdx >= 0 && idx < currentIdx) status = 'completed';
      else if (idx === currentIdx) status = 'blocked';
    } else if (currentIdx >= 0) {
      if (idx < currentIdx) status = 'completed';
      else if (idx === currentIdx) status = 'active';
    } else if (current === s.key) {
      status = 'active';
    }
    return { name: s.key, status, label: s.label };
  });
}

export function normalizeJob(raw: unknown): Job {
  if (!raw || typeof raw !== 'object') return {};
  const job = raw as Job;
  const state = (job.upstream_state || {}) as Record<string, unknown>;
  const requirements = asRecord(state.requirements);
  const qualityReport = asRecord(state.quality_report);
  const groundingReview = asRecord(qualityReport.grounding_review);
  const securityReport = asRecord(state.security_report);
  const relevanceReport = asRecord(state.relevance_report);
  const createdAt = numericValue(job.created_at);
  const updatedAt = numericValue(job.updated_at);
  return {
    ...job,
    job_id: job.job_id || job.id,
    status: normalizeStatus(job.status),
    progress: normalizeGenerationProgress(job),
    draft_proposal: stringValue(state.draft_proposal) || job.draft_proposal,
    document_processing: {
      tender: normalizeProcessingReport(state.document_processing),
      template: normalizeProcessingReport(state.response_template_processing),
    },
    extraction: Object.keys(requirements).length ? normalizeRequirements(requirements) : job.extraction,
    research: normalizeResearch(state, relevanceReport, job.research),
    security: normalizeSecurity(state, securityReport, job.security),
    quality: normalizeQuality(state, qualityReport, groundingReview, job.quality),
    evaluation: normalizeEvaluation(job.evaluation_results || job.evaluation),
    duration:
      createdAt != null && updatedAt != null
        ? Math.max(0, updatedAt - createdAt)
        : job.duration,
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function numericValue(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function stringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value.map((item) => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      const claim = stringValue(record.claim);
      const reason = stringValue(record.reason) || stringValue(record.evidence);
      return [claim, reason].filter(Boolean).join(' — ') || JSON.stringify(item);
    }
    return String(item);
  });
}

function evidenceWarningList(value: unknown) {
  if (!Array.isArray(value)) return undefined;
  return value
    .map((item) => {
      const warning = asRecord(item);
      if (!Object.keys(warning).length) return undefined;
      return {
        section: stringValue(warning.section),
        placeholder_count: numericValue(warning.placeholder_count),
        message: stringValue(warning.message),
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
}

function normalizeProcessingReport(value: unknown) {
  const report = asRecord(value);
  if (!Object.keys(report).length) return undefined;
  const document = asRecord(report.document);
  const metadata = asRecord(document.metadata);
  const index = asRecord(report.index_result);
  const pages = Array.isArray(document.pages) ? document.pages : [];
  const ocrConfidences = pages
    .map((page) => numericValue(asRecord(page).ocr_confidence))
    .filter((score): score is number => score != null);
  return {
    success: Boolean(report.success),
    filename: stringValue(document.filename) || stringValue(metadata.filename),
    file_type: stringValue(metadata.file_type),
    file_size: numericValue(metadata.file_size_bytes),
    checksum: stringValue(metadata.content_sha256),
    page_count: numericValue(metadata.page_count),
    paragraph_count: numericValue(metadata.paragraph_count),
    table_count: numericValue(metadata.table_count),
    section_count: numericValue(metadata.section_count),
    native_pages: numericValue(metadata.native_pages),
    ocr_pages: numericValue(metadata.ocr_pages),
    ocr_confidence: ocrConfidences.length
      ? ocrConfidences.reduce((sum, score) => sum + score, 0) / ocrConfidences.length
      : null,
    extraction_warnings: stringList(document.warnings),
    indexed_blocks: numericValue(index.blocks_sent),
    anythingllm_workspace: stringValue(index.workspace_slug),
    indexing_errors: index.error ? [String(index.error)] : undefined,
  };
}

function normalizeRequirements(requirements: Record<string, unknown>) {
  const deadlines = asRecord(requirements.deadlines);
  const template = asRecord(requirements.response_template);
  const templateInstructions = stringList(template.instructions) ?? [];
  return {
    ...requirements,
    submission_deadline:
      stringValue(requirements.submission_deadline) || stringValue(deadlines.submission_deadline),
    project_duration:
      stringValue(requirements.project_duration) || stringValue(deadlines.project_duration),
    response_template_rules:
      templateInstructions.length > 0
        ? templateInstructions
        : stringList(template.template_instructions),
    template_source: stringValue(template.template_source),
    template_version: stringValue(template.version),
    required_sections: stringList(template.required_sections),
    required_section_order: stringList(template.section_order),
    formatting_instructions: stringList(template.formatting_requirements),
  };
}

function normalizeResearch(
  state: Record<string, unknown>,
  relevance: Record<string, unknown>,
  existing: Job['research'],
) {
  const summary = stringValue(state.research_summary);
  if (!summary && !Object.keys(relevance).length) return existing;
  const relevant = state.research_relevant;
  const skipped = summary?.toLowerCase().includes('skipped') || false;
  return {
    ...existing,
    status: skipped ? 'skipped' : relevant === true ? 'accepted' : 'rejected',
    accepted: relevant === true,
    rejected: relevant === false && !skipped,
    skipped,
    relevance_score: numericValue(relevance.coverage),
    relevance_threshold: numericValue(relevance.minimum_coverage),
    matched_keywords: stringList(relevance.matched_keywords),
    relevance_explanation: stringValue(relevance.reason),
    summary,
    failure_reason: relevant === false ? stringValue(relevance.reason) : undefined,
  };
}

function findingList(findings: Record<string, unknown>, key: string) {
  const value = findings[key];
  if (value == null || value === 0 || value === false) return [];
  if (Array.isArray(value)) return value;
  return [{ type: key, count: typeof value === 'number' ? value : 1, detail: typeof value === 'string' ? value : undefined }];
}

function normalizeSecurity(
  state: Record<string, unknown>,
  report: Record<string, unknown>,
  existing: Job['security'],
) {
  if (!Object.keys(report).length) return existing;
  const scanner = asRecord(report.scanner);
  const findings = asRecord(report.findings);
  const scanPerformed = report.scan_performed === true;
  return {
    ...existing,
    scanning_performed: scanPerformed,
    scanner_mode: stringValue(scanner.mode),
    llm_guard_enabled: Boolean(scanner.llm_guard_enabled),
    fallback_scanner_enabled: Boolean(scanner.fallback_enabled),
    status: !scanPerformed ? 'disabled' : state.security_passed === true ? 'pass' : 'blocked',
    pii_findings: findingList(findings, 'pii'),
    email_findings: findingList(findings, 'email'),
    phone_findings: findingList(findings, 'phone'),
    secret_findings: findingList(findings, 'secrets'),
    malicious_url_findings: findingList(findings, 'malicious_urls'),
    prompt_injection_findings: findingList(findings, 'prompt_injection'),
    toxicity_findings: findingList(findings, 'toxicity'),
    refusal_findings: findingList(findings, 'refusal'),
    notes: stringList(report.notes),
  };
}

function normalizeQuality(
  state: Record<string, unknown>,
  report: Record<string, unknown>,
  review: Record<string, unknown>,
  existing: Job['quality'],
) {
  if (!Object.keys(report).length) return existing;
  return {
    ...existing,
    status: state.quality_passed === true ? 'passed' : 'failed',
    word_count: numericValue(report.word_count),
    required_sections: stringList(report.required_sections),
    present_sections: stringList(report.present_sections),
    passed_sections: stringList(report.passed_sections),
    missing_sections: stringList(report.missing_sections),
    out_of_order_sections: stringList(report.out_of_order_sections),
    duplicate_sections: stringList(report.duplicate_sections),
    incomplete_sections: stringList(report.incomplete_sections),
    failed_sections: stringList(report.failed_sections),
    groundedness_score: numericValue(review.groundedness_score),
    groundedness_threshold: numericValue(report.groundedness_threshold),
    coherence_score: numericValue(review.coherence_score),
    coherence_threshold: numericValue(report.coherence_threshold),
    unsupported_claims: stringList(review.unsupported_claims),
    contradictions: stringList(review.contradictions),
    coherence_issues: stringList(review.coherence_issues),
    evidence_warnings: evidenceWarningList(report.evidence_warnings),
    evaluator_available: report.evaluation_available !== false,
    evaluator_errors: report.evaluator_error ? [String(report.evaluator_error)] : undefined,
    review_notes: stringList(report.notes),
    generation_attempt: numericValue(state.generation_attempts),
  };
}

function normalizeEvaluation(value: unknown) {
  const evaluation = asRecord(value);
  if (!Object.keys(evaluation).length) return undefined;
  const rag = asRecord(evaluation.rag);
  const output = asRecord(evaluation.output);
  const performance = asRecord(evaluation.performance);
  const precision = numericValue(rag.candidate_precision_proxy) ?? numericValue(rag.precision_at_k);
  const recall = numericValue(rag.candidate_recall_proxy) ?? numericValue(rag.recall_at_k);
  const durationMap = asRecord(
    Object.keys(asRecord(performance.exact_agent_duration_seconds)).length
      ? performance.exact_agent_duration_seconds
      : performance.observed_stage_duration_seconds,
  );
  const usage = asRecord(performance.llm_token_usage);
  const modelBreakdown = Array.isArray(usage.providers)
    ? usage.providers.map((item: unknown) => {
        const record = asRecord(item);
        return {
          model: stringValue(record.model),
          provider: stringValue(record.provider),
          requests: numericValue(record.request_count) ?? numericValue(record.requests),
          input_tokens: numericValue(record.input_tokens),
          output_tokens: numericValue(record.output_tokens),
        };
      })
    : undefined;
  return {
    rag: {
      precision,
      recall,
      f1: numericValue(rag.f1_score) ?? (
        precision != null && recall != null && precision + recall > 0
          ? (2 * precision * recall) / (precision + recall)
          : undefined),
      context_relevance: numericValue(rag.context_relevance),
      context_utilization: numericValue(rag.context_utilization),
      evaluation_mode: stringValue(rag.evaluation_mode),
      method: stringValue(rag.method),
      candidate_chunks: numericValue(rag.candidate_chunk_count) ?? (
        Array.isArray(rag.cases)
          ? rag.cases.reduce((sum: number, item: unknown) => {
              const record = asRecord(item);
              const count = numericValue(record.candidate_chunk_count);
              const ids = record.candidate_chunk_ids;
              return sum + (count ?? (Array.isArray(ids) ? ids.length : 0));
            }, 0)
          : undefined
      ),
      used_chunks: numericValue(rag.used_chunk_count) ?? (
        Array.isArray(rag.cases)
          ? rag.cases.reduce((sum: number, item: unknown) => {
              const record = asRecord(item);
              const count = numericValue(record.used_chunk_count);
              const ids = record.used_chunk_ids;
              return sum + (count ?? (Array.isArray(ids) ? ids.length : 0));
            }, 0)
          : undefined
      ),
      relevant_chunks: Array.isArray(rag.cases)
        ? rag.cases.reduce((sum: number, item: unknown) => {
            const ids = asRecord(item).relevant_chunk_ids;
            return sum + (Array.isArray(ids) ? ids.length : 0);
          }, 0)
        : undefined,
      retrieved_chunks: Array.isArray(rag.cases)
        ? rag.cases.reduce((sum: number, item: unknown) => {
            const ids = asRecord(item).retrieved_chunk_ids;
            return sum + (Array.isArray(ids) ? ids.length : 0);
          }, 0)
        : undefined,
      query_results: Array.isArray(rag.cases)
        ? rag.cases.map((item: unknown) => {
            const record = asRecord(item);
            return {
              query: stringValue(record.section) || stringValue(record.query),
              section: stringValue(record.section),
              precision: numericValue(record.candidate_precision_proxy) ?? numericValue(record.precision_at_k),
              recall: numericValue(record.candidate_recall_proxy) ?? numericValue(record.recall_at_k),
              context_relevance: numericValue(record.context_relevance),
              context_utilization: numericValue(record.context_utilization),
              candidate_chunks: numericValue(record.candidate_chunk_count) ?? (
                Array.isArray(record.candidate_chunk_ids) ? record.candidate_chunk_ids.length : undefined
              ),
              used_chunks: numericValue(record.used_chunk_count) ?? (
                Array.isArray(record.used_chunk_ids) ? record.used_chunk_ids.length : undefined
              ),
              relevant_chunks: Array.isArray(record.relevant_chunk_ids) ? record.relevant_chunk_ids.length : undefined,
              retrieved_chunks: Array.isArray(record.retrieved_chunk_ids) ? record.retrieved_chunk_ids.length : undefined,
            };
          })
        : undefined,
    },
    output_quality: {
      template_compliance: numericValue(output.template_compliance_score),
      section_coverage: numericValue(output.template_compliance_score),
      coherence: numericValue(output.coherence_score),
      groundedness: numericValue(output.groundedness_score),
      hallucination_rate:
        numericValue(output.hallucinations_per_1000_words) != null
          ? numericValue(output.hallucinations_per_1000_words)! / 1000
          : undefined,
      security_evaluation:
        typeof output.security_passed === 'boolean' ? (output.security_passed ? 1 : 0) : undefined,
      overall_score:
        typeof output.quality_passed === 'boolean' ? (output.quality_passed ? 1 : 0) : undefined,
    },
    performance: {
      total_duration: numericValue(performance.total_duration_seconds),
      generation_duration: numericValue(durationMap.generation),
      duration_per_agent: Object.entries(durationMap).map(([agent, duration]) => ({
        agent,
        duration: numericValue(duration),
      })),
      pipeline_throughput_per_hour: numericValue(performance.pipeline_throughput_per_hour),
      llm_request_count: numericValue(usage.request_count) ?? numericValue(usage.total_requests),
      input_tokens: numericValue(usage.input_tokens),
      output_tokens: numericValue(usage.output_tokens),
      total_tokens: numericValue(usage.total_tokens),
      model_breakdown: modelBreakdown,
    },
  };
}

export function normalizeJobsList(raw: unknown): Job[] {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw.map(normalizeJob);
  const obj = raw as { jobs?: Job[]; items?: Job[] };
  if (obj.jobs) return obj.jobs.map(normalizeJob);
  if (obj.items) return obj.items.map(normalizeJob);
  return [];
}

export function formatDuration(seconds?: number): string {
  if (seconds == null || isNaN(seconds)) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export function formatBytes(bytes?: number): string {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatPercent(value?: number | null, fallback = 'Not measured'): string {
  if (value == null || isNaN(value)) return fallback;
  // Accept 0-1 or 0-100
  const pct = value > 1 ? value : value * 100;
  return `${pct.toFixed(1)}%`;
}

export function formatNumber(value?: number | null, fallback = '—'): string {
  if (value == null || isNaN(value)) return fallback;
  return value.toLocaleString();
}

export function formatDateTime(iso?: string | number): string {
  if (iso == null || iso === '') return '—';
  try {
    const value = typeof iso === 'number' && iso < 10_000_000_000 ? iso * 1000 : iso;
    return new Date(value).toLocaleString();
  } catch {
    return String(iso);
  }
}

export function isTerminalStatus(status?: JobStatus): boolean {
  return status === 'completed' || status === 'failed' || status === 'blocked' || status === 'cancelled';
}
