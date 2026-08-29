import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Briefcase,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Gauge,
  TrendingUp,
  ArrowRight,
  HeartPulse,
} from 'lucide-react';
import { useJobs } from '@/hooks/useJobs';
import { useHealth } from '@/hooks/useHealth';
import { MetricCard } from '@/components/MetricCard';
import { CardSkeleton, TableSkeleton } from '@/components/LoadingSkeleton';
import { ErrorState } from '@/components/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { JobStatusBadge } from '@/components/StatusBadge';
import { formatDuration, formatPercent, stageLabel } from '@/api/normalize';
import type { DashboardStats, Job, HealthResponse } from '@/types';

function computeStats(jobs: Job[]): DashboardStats {
  const total = jobs.length;
  const running = jobs.filter((j) => j.status === 'running' || j.status === 'submitting' || j.status === 'queued').length;
  const completed = jobs.filter((j) => j.status === 'completed').length;
  const failed = jobs.filter((j) => j.status === 'failed').length;

  const completedJobs = jobs.filter((j) => j.status === 'completed');
  const durations = completedJobs.map((j) => j.duration).filter((d): d is number => d != null);
  const avgDuration = durations.length > 0 ? durations.reduce((a, b) => a + b, 0) / durations.length : null;

  const groundedness = completedJobs
    .map((j) => j.evaluation?.output_quality?.groundedness)
    .filter((v): v is number => v != null);
  const avgGroundedness = groundedness.length > 0 ? groundedness.reduce((a, b) => a + b, 0) / groundedness.length : null;

  const coherence = completedJobs
    .map((j) => j.evaluation?.output_quality?.coherence)
    .filter((v): v is number => v != null);
  const avgCoherence = coherence.length > 0 ? coherence.reduce((a, b) => a + b, 0) / coherence.length : null;

  const ragPrecisions = completedJobs
    .map((j) => j.evaluation?.rag?.precision)
    .filter((v): v is number => v != null);
  const ragPrecision = ragPrecisions.length > 0 ? ragPrecisions.reduce((a, b) => a + b, 0) / ragPrecisions.length : null;

  const ragRecalls = completedJobs
    .map((j) => j.evaluation?.rag?.recall)
    .filter((v): v is number => v != null);
  const ragRecall = ragRecalls.length > 0 ? ragRecalls.reduce((a, b) => a + b, 0) / ragRecalls.length : null;

  return {
    total_jobs: total,
    running_jobs: running,
    completed_jobs: completed,
    failed_jobs: failed,
    average_generation_time: avgDuration,
    average_groundedness: avgGroundedness,
    average_coherence: avgCoherence,
    rag_precision: ragPrecision,
    rag_recall: ragRecall,
  };
}

function HealthBadge({ status }: { status?: string }) {
  const colors: Record<string, string> = {
    healthy: 'bg-emerald-100 text-emerald-700',
    unhealthy: 'bg-rose-100 text-rose-700',
    degraded: 'bg-amber-100 text-amber-700',
    unknown: 'bg-slate-100 text-slate-500',
  };
  const s = (status || 'unknown').toLowerCase();
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${colors[s] || colors.unknown}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s === 'healthy' ? 'bg-emerald-500' : s === 'unhealthy' ? 'bg-rose-500' : s === 'degraded' ? 'bg-amber-500' : 'bg-slate-400'}`} />
      {s}
    </span>
  );
}

function PipelineHealthSummary({ health }: { health: HealthResponse | null }) {
  if (!health) return null;
  const healthErrors = health.errors
    ? Array.isArray(health.errors)
      ? health.errors
      : Object.entries(health.errors).map(([component, message]) => `${component}: ${message}`)
    : [];
  const components = [
    { label: 'Redis', data: health.redis },
    { label: 'Celery Queue', data: health.celery_queue },
    { label: 'Agent Pipeline', data: health.agent_pipeline },
    { label: 'Document Extractor', data: health.extractor },
    { label: 'Database', data: health.database },
    { label: 'Storage', data: health.storage },
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <HeartPulse className="h-5 w-5 text-teal-500" />
        <h3 className="text-sm font-semibold text-slate-800">Pipeline Health</h3>
        <HealthBadge status={health.status} />
      </div>
      <ul className="space-y-2">
        {components.map((c) => {
          const comp = c.data;
          const status = comp?.status || (health.components?.[c.label.toLowerCase().replace(' ', '_')]?.status) || 'unknown';
          return (
            <li key={c.label} className="flex items-center justify-between text-sm">
              <span className="text-slate-600">{c.label}</span>
              <div className="flex items-center gap-2">
                {comp?.provider && <span className="text-xs text-slate-400">{comp.provider}</span>}
                <HealthBadge status={status} />
              </div>
            </li>
          );
        })}
      </ul>
      {healthErrors.length > 0 && (
        <div className="mt-3 rounded-lg bg-rose-50 p-2 border border-rose-200">
          <p className="text-xs font-semibold text-rose-700 mb-1">Current errors</p>
          <ul className="space-y-0.5">
            {healthErrors.map((e, i) => (
              <li key={i} className="text-xs text-rose-600">• {e}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function DashboardPage() {
  const { jobs, loading, error, refresh } = useJobs();
  const { health } = useHealth(true, 30000);
  const stats = useMemo(() => computeStats(jobs), [jobs]);
  const recentJobs = jobs.slice(0, 8);

  if (loading && jobs.length === 0) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <TableSkeleton rows={5} />
        </div>
      </div>
    );
  }

  if (error && jobs.length === 0) {
    return <ErrorState message={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-6">
      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Total Jobs" value={stats.total_jobs} icon={Briefcase} accent="slate" />
        <MetricCard label="Running" value={stats.running_jobs} icon={Activity} accent="blue" />
        <MetricCard label="Completed" value={stats.completed_jobs} icon={CheckCircle2} accent="emerald" />
        <MetricCard label="Failed" value={stats.failed_jobs} icon={XCircle} accent="rose" />
      </div>

      {/* Secondary stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Avg Generation Time"
          value={formatDuration(stats.average_generation_time || undefined)}
          icon={Clock}
          accent="slate"
        />
        <MetricCard
          label="Avg Groundedness"
          value={formatPercent(stats.average_groundedness, '—')}
          icon={TrendingUp}
          accent="teal"
        />
        <MetricCard
          label="Avg Coherence"
          value={formatPercent(stats.average_coherence, '—')}
          icon={Gauge}
          accent="teal"
        />
        <MetricCard
          label="RAG Precision / Recall"
          value={stats.rag_precision != null ? `${formatPercent(stats.rag_precision, '')} / ${formatPercent(stats.rag_recall, '')}` : 'Not measured'}
          icon={Gauge}
          accent="blue"
        />
      </div>

      {/* Recent jobs + health */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h3 className="text-sm font-semibold text-slate-800">Recent Jobs</h3>
            <Link to="/jobs" className="inline-flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-700">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {recentJobs.length === 0 ? (
            <EmptyState icon={Briefcase} title="No jobs yet" description="Create a new proposal to get started." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                    <th className="px-4 py-2 font-medium">Tender</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Stage</th>
                    <th className="px-4 py-2 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {recentJobs.map((job) => (
                    <tr key={job.job_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-2.5">
                        <Link to={`/jobs/${job.job_id}`} className="text-slate-700 hover:text-teal-600 truncate block max-w-xs">
                          {job.tender_filename || job.job_id}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <JobStatusBadge status={job.status || 'queued'} />
                      </td>
                      <td className="px-4 py-2.5 text-xs text-slate-600">{stageLabel(job.current_stage || job.stage || '')}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-400">
                        {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <PipelineHealthSummary health={health} />
      </div>
    </div>
  );
}
