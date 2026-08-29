import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Briefcase, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { useJobs } from '@/hooks/useJobs';
import { JobStatusBadge } from '@/components/StatusBadge';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { TableSkeleton } from '@/components/LoadingSkeleton';
import { formatDateTime, formatDuration, formatPercent, stageLabel } from '@/api/normalize';
import type { JobStatus } from '@/types';

const FILTERS: { key: JobStatus | 'all'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'queued', label: 'Queued' },
  { key: 'running', label: 'Running' },
  { key: 'evaluating', label: 'Evaluating' },
  { key: 'completed', label: 'Completed' },
  { key: 'failed', label: 'Failed' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'cancelled', label: 'Cancelled' },
];

const PAGE_SIZE = 20;

export function JobsListPage() {
  const { jobs, loading, error, refresh } = useJobs();
  const [filter, setFilter] = useState<JobStatus | 'all'>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    let result = jobs;
    if (filter !== 'all') {
      result = result.filter((j) => j.status === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) =>
          (j.tender_filename || '').toLowerCase().includes(q) ||
          (j.template_filename || '').toLowerCase().includes(q) ||
          (j.job_id || '').toLowerCase().includes(q),
      );
    }
    return result;
  }, [jobs, filter, search]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const pageJobs = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (loading && jobs.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <TableSkeleton rows={6} />
      </div>
    );
  }

  if (error && jobs.length === 0) {
    return <ErrorState message={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-900">Active Jobs</h2>
        <Link
          to="/new"
          className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
        >
          New Proposal
        </Link>
      </div>

      {/* Search + filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by filename or ID…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => {
                setFilter(f.key);
                setPage(0);
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                filter === f.key
                  ? 'bg-teal-600 text-white'
                  : 'border border-slate-300 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        {pageJobs.length === 0 ? (
          <EmptyState
            icon={Briefcase}
            title="No jobs found"
            description="Try adjusting your filters or create a new proposal."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs text-slate-500 bg-slate-50">
                  <th className="px-4 py-2.5 font-medium">Job ID</th>
                  <th className="px-4 py-2.5 font-medium">Tender</th>
                  <th className="px-4 py-2.5 font-medium">Template</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Stage</th>
                  <th className="px-4 py-2.5 font-medium">Created</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Quality</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {pageJobs.map((job) => (
                  <tr key={job.job_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-2.5">
                      <Link
                        to={`/jobs/${job.job_id}`}
                        className="font-mono text-xs text-teal-600 hover:underline"
                      >
                        {job.job_id?.substring(0, 8)}…
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 max-w-[160px] truncate text-slate-700">{job.tender_filename || '—'}</td>
                    <td className="px-4 py-2.5 max-w-[160px] truncate text-slate-700">{job.template_filename || 'Built-in default'}</td>
                    <td className="px-4 py-2.5">
                      <JobStatusBadge status={job.status || 'queued'} />
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-600">{stageLabel(job.current_stage || job.stage || '')}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-400">{formatDateTime(job.created_at)}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-600">{formatDuration(job.duration)}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-600">{formatPercent(job.quality_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5">
            <span className="text-xs text-slate-500">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(Math.max(0, page - 1))}
                disabled={page === 0}
                className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-xs text-slate-600 px-2">{page + 1} / {totalPages}</span>
              <button
                onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                disabled={page >= totalPages - 1}
                className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
