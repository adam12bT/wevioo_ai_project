import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardCheck, ArrowRight } from 'lucide-react';
import { useJobs } from '@/hooks/useJobs';
import { JobStatusBadge } from '@/components/StatusBadge';
import { ScoreBar } from '@/components/ScoreBar';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { TableSkeleton } from '@/components/LoadingSkeleton';
import { formatPercent } from '@/api/normalize';
import type { Job } from '@/types';

export function EvaluationsPage() {
  const { jobs, loading, error, refresh } = useJobs(true);

  const evaluatedJobs = useMemo(
    () => jobs.filter((j: Job) => j.evaluation && Object.keys(j.evaluation).length > 0),
    [jobs],
  );

  if (loading && jobs.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <TableSkeleton rows={5} />
      </div>
    );
  }

  if (error && jobs.length === 0) {
    return <ErrorState message={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-slate-900">Evaluations</h2>

      {evaluatedJobs.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="No evaluations yet"
          description="Completed jobs with evaluation data will appear here."
        />
      ) : (
        <div className="space-y-4">
          {evaluatedJobs.map((job) => (
            <div key={job.job_id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="min-w-0">
                  <Link
                    to={`/jobs/${job.job_id}`}
                    className="text-sm font-semibold text-slate-800 hover:text-teal-600 truncate block"
                  >
                    {job.tender_filename || job.job_id}
                  </Link>
                  <p className="text-xs text-slate-400 mt-0.5">{job.job_id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <JobStatusBadge status={job.status || 'queued'} />
                  <Link
                    to={`/jobs/${job.job_id}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-700"
                  >
                    Details <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {/* RAG */}
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-600">RAG Quality</p>
                  <ScoreBar value={job.evaluation?.rag?.precision} label="Precision" />
                  <ScoreBar value={job.evaluation?.rag?.recall} label="Recall" />
                  <ScoreBar value={job.evaluation?.rag?.f1} label="F1" />
                </div>

                {/* Output Quality */}
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-600">Output Quality</p>
                  <ScoreBar value={job.evaluation?.output_quality?.template_compliance} label="Compliance" />
                  <ScoreBar value={job.evaluation?.output_quality?.coherence} label="Coherence" />
                  <ScoreBar value={job.evaluation?.output_quality?.groundedness} label="Groundedness" />
                </div>

                {/* Overall */}
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-600">Overall</p>
                  <ScoreBar value={job.evaluation?.output_quality?.overall_score} label="Overall Score" />
                  <ScoreBar value={job.evaluation?.output_quality?.hallucination_rate} label="Hallucination" />
                  <ScoreBar value={job.evaluation?.output_quality?.security_evaluation} label="Security" />
                </div>

                {/* Performance */}
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold text-slate-600">Performance</p>
                  <div className="text-xs text-slate-600">
                    <span className="text-slate-400">Total duration: </span>
                    <span className="font-medium">{formatDurationOrDash(job)}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    <span className="text-slate-400">LLM requests: </span>
                    <span className="font-medium">{job.evaluation?.performance?.llm_request_count ?? '—'}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    <span className="text-slate-400">Total tokens: </span>
                    <span className="font-medium">{job.evaluation?.performance?.total_tokens?.toLocaleString() ?? '—'}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    <span className="text-slate-400">Quality score: </span>
                    <span className="font-medium">{formatPercent(job.quality_score)}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDurationOrDash(job: Job): string {
  const d = job.evaluation?.performance?.total_duration ?? job.duration;
  if (d == null) return '—';
  if (d < 60) return `${Math.round(d)}s`;
  if (d < 3600) return `${Math.floor(d / 60)}m ${Math.round(d % 60)}s`;
  const h = Math.floor(d / 3600);
  const m = Math.round((d % 3600) / 60);
  return `${h}h ${m}m`;
}
