// Centralized types for the RFP/tender response platform.

export type JobStatus =
  | 'queued'
  | 'submitting'
  | 'running'
  | 'evaluating'
  | 'completed'
  | 'failed'
  | 'blocked'
  | 'cancelled';

export type StageStatus =
  | 'waiting'
  | 'active'
  | 'completed'
  | 'warning'
  | 'failed'
  | 'blocked';

export type GenerationSectionStatus =
  | 'waiting'
  | 'generating'
  | 'complete'
  | 'incomplete'
  | 'failed';

export interface GenerationSection {
  title: string;
  status: GenerationSectionStatus;
  content?: string;
  error?: string;
  evidence?: string[];
  attempt?: number;
}

export interface GenerationProgress {
  overall_percent?: number;
  current_section?: string;
  current_batch?: string | number;
  completed_sections?: number;
  total_sections?: number;
  attempt?: number;
  sections?: GenerationSection[];
  message?: string;
}

export interface PipelineStage {
  name: string;
  status: StageStatus;
  label?: string;
  started_at?: string;
  finished_at?: string;
  message?: string;
  progress?: number;
}

export interface PipelineState {
  current_stage?: string;
  stages?: PipelineStage[];
  overall_percent?: number;
}

export interface DocumentProcessingInfo {
  success?: boolean;
  filename?: string;
  file_type?: string;
  file_size?: number;
  checksum?: string;
  page_count?: number;
  paragraph_count?: number;
  table_count?: number;
  section_count?: number;
  native_pages?: number;
  ocr_pages?: number;
  ocr_confidence?: number | null;
  extraction_warnings?: string[];
  indexed_blocks?: number;
  anythingllm_workspace?: string;
  indexing_errors?: string[];
}

export interface TenderRequirements {
  scope_summary?: string;
  deliverables?: string[];
  mandatory_requirements?: string[];
  technical_constraints?: string[];
  contractual_constraints?: string[];
  domain_specific_constraints?: string[];
  required_evidence?: string[];
  required_forms?: string[];
  additional_requirements?: string[];
  budget?: string;
  submission_deadline?: string;
  project_duration?: string;
  evaluation_criteria?: string[];
  response_template_rules?: string[];
  required_sections?: string[];
  required_section_order?: string[];
  formatting_instructions?: string[];
  template_source?: string;
  template_version?: string;
}

export interface ResearchSource {
  title?: string;
  url?: string;
  snippet?: string;
}

export interface ResearchInfo {
  status?: string;
  accepted?: boolean;
  rejected?: boolean;
  skipped?: boolean;
  relevance_score?: number;
  relevance_threshold?: number;
  matched_keywords?: string[];
  relevance_explanation?: string;
  summary?: string;
  sources?: ResearchSource[];
  warnings?: string[];
  failure_reason?: string;
}

export interface SecurityFinding {
  type?: string;
  severity?: string;
  detail?: string;
  count?: number;
}

export interface SecurityInfo {
  scanning_performed?: boolean;
  scanner_mode?: string;
  llm_guard_enabled?: boolean;
  fallback_scanner_enabled?: boolean;
  status?: 'pass' | 'warning' | 'blocked' | 'human_review' | string;
  pii_findings?: SecurityFinding[];
  email_findings?: SecurityFinding[];
  phone_findings?: SecurityFinding[];
  secret_findings?: SecurityFinding[];
  malicious_url_findings?: SecurityFinding[];
  prompt_injection_findings?: SecurityFinding[];
  toxicity_findings?: SecurityFinding[];
  refusal_findings?: SecurityFinding[];
  notes?: string[];
}

export interface EvidenceWarning {
  section?: string;
  placeholder_count?: number;
  message?: string;
}

export interface QualityInfo {
  status?: string;
  word_count?: number;
  required_sections?: string[];
  present_sections?: string[];
  passed_sections?: string[];
  missing_sections?: string[];
  out_of_order_sections?: string[];
  duplicate_sections?: string[];
  incomplete_sections?: string[];
  failed_sections?: string[];
  groundedness_score?: number;
  groundedness_threshold?: number;
  coherence_score?: number;
  coherence_threshold?: number;
  unsupported_claims?: string[];
  contradictions?: string[];
  coherence_issues?: string[];
  evidence_warnings?: EvidenceWarning[];
  evaluator_available?: boolean;
  evaluator_errors?: string[];
  review_notes?: string[];
  generation_attempt?: number;
  max_attempts_reached?: boolean;
}

export interface RagQueryResult {
  query?: string;
  section?: string;
  precision?: number;
  recall?: number;
  context_relevance?: number;
  context_utilization?: number;
  candidate_chunks?: number;
  used_chunks?: number;
  relevant_chunks?: number;
  retrieved_chunks?: number;
}

export interface RagEvaluation {
  precision?: number;
  recall?: number;
  f1?: number;
  context_relevance?: number;
  context_utilization?: number;
  evaluation_mode?: 'automatic_proxy' | 'labelled_ground_truth' | string;
  method?: string;
  candidate_chunks?: number;
  used_chunks?: number;
  relevant_chunks?: number;
  retrieved_chunks?: number;
  query_results?: RagQueryResult[];
}

export interface OutputQualityEvaluation {
  template_compliance?: number;
  section_coverage?: number;
  coherence?: number;
  groundedness?: number;
  hallucination_rate?: number;
  security_evaluation?: number;
  overall_score?: number;
}

export interface AgentDuration {
  agent?: string;
  duration?: number;
}

export interface ModelBreakdown {
  model?: string;
  provider?: string;
  requests?: number;
  input_tokens?: number;
  output_tokens?: number;
}

export interface PerformanceEvaluation {
  total_duration?: number;
  duration_per_agent?: AgentDuration[];
  generation_duration?: number;
  pipeline_throughput_per_hour?: number;
  llm_request_count?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  model_breakdown?: ModelBreakdown[];
}

export interface Evaluation {
  rag?: RagEvaluation;
  output_quality?: OutputQualityEvaluation;
  performance?: PerformanceEvaluation;
}

export interface DocumentVersion {
  version: string | number;
  created_at?: string;
  file_size?: number;
  checksum?: string;
  evaluation_summary?: string;
}

export interface Job {
  job_id?: string;
  id?: string;
  status?: JobStatus;
  current_stage?: string;
  stage?: string;
  created_at?: string | number;
  updated_at?: string | number;
  tender_filename?: string;
  template_filename?: string | null;
  progress?: GenerationProgress | number | null;
  pipeline?: PipelineState;
  upstream_state?: {
    generation_progress?: GenerationProgress | null;
    [key: string]: unknown;
  };
  draft_proposal?: string;
  document_version?: number | null;
  result_path?: string | null;
  result_object_key?: string | null;
  completed_stages?: string[];
  evaluation_results?: Evaluation;
  document_processing?: {
    tender?: DocumentProcessingInfo;
    template?: DocumentProcessingInfo;
  };
  extraction?: TenderRequirements;
  research?: ResearchInfo;
  security?: SecurityInfo;
  quality?: QualityInfo;
  evaluation?: Evaluation;
  versions?: DocumentVersion[];
  error?: string;
  failure_reason?: string;
  duration?: number;
  quality_score?: number;
  [key: string]: unknown;
}

export interface JobsListResponse {
  jobs?: Job[];
  items?: Job[];
  total?: number;
  page?: number;
  pages?: number;
}

export interface HealthComponent {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown' | string;
  message?: string;
  provider?: string;
  ready?: boolean;
  configured?: boolean;
  endpoint?: string;
}

export interface HealthResponse {
  status?: 'healthy' | 'unhealthy' | 'degraded' | string;
  redis?: HealthComponent;
  celery_queue?: HealthComponent;
  agent_pipeline?: HealthComponent;
  extractor?: HealthComponent;
  database?: HealthComponent;
  storage?: HealthComponent;
  errors?: string[] | Record<string, string>;
  components?: Record<string, HealthComponent>;
  [key: string]: unknown;
}

export interface DashboardStats {
  total_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  average_generation_time: number | null;
  average_groundedness: number | null;
  average_coherence: number | null;
  rag_precision: number | null;
  rag_recall: number | null;
}

export interface KnowledgeDocument {
  id?: string;
  name?: string;
  category?: string;
  size?: number;
  status?: string;
  created_at?: string;
  progress?: number;
  error?: string;
}

export type ToastVariant = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  title: string;
  message?: string;
  variant: ToastVariant;
}
