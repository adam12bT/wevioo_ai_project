import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Library, ArrowRight, FileText } from 'lucide-react';
import { useJobs } from '@/hooks/useJobs';
import { JobStatusBadge } from '@/components/StatusBadge';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { TableSkeleton } from '@/components/LoadingSkeleton';
import { formatDateTime, formatDuration, formatPercent } from '@/api/normalize';

export function ProposalLibraryPage() {
  const { jobs, loading, error, refresh } = useJobs(true);
  const [search, setSearch] = useState('');

  const completed = useMemo(() => {
    let result = jobs.filter(
      (job) =>
        Boolean(
          job.document_version ||
            job.result_path ||
            job.result_object_key ||
            job.draft_proposal,
        ) || job.status === 'completed',
    );
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) =>
          (j.tender_filename || '').toLowerCase().includes(q) ||
          (j.template_filename || '').toLowerCase().includes(q),
      );
    }
    return result;
  }, [jobs, search]);

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
      <h2 className="text-xl font-bold text-slate-900">Proposal Library</h2>

      <input
        type="text"
        placeholder="Search proposals…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-xs rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400"
      />

      {completed.length === 0 ? (
        <EmptyState
          icon={Library}
          title="No proposals yet"
          description="Generated and versioned proposals will appear here, including drafts that require quality review."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {completed.map((job) => (
            <Link
              key={job.job_id}
              to={`/jobs/${job.job_id}`}
              className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:shadow-md hover:border-teal-300"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
                  <FileText className="h-5 w-5 text-teal-600" />
                </div>
                <JobStatusBadge status={job.status || 'completed'} />
              </div>
              <h3 className="text-sm font-semibold text-slate-800 truncate group-hover:text-teal-600">
                {job.tender_filename || 'Untitled'}
              </h3>
              <p className="mt-1 text-xs text-slate-400">{formatDateTime(job.created_at)}</p>
              <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                <span>Duration: {formatDuration(job.duration)}</span>
                {job.quality_score != null && <span>Quality: {formatPercent(job.quality_score)}</span>}
              </div>
              <div className="mt-2 flex items-center gap-1 text-xs font-medium text-teal-600 opacity-0 transition-opacity group-hover:opacity-100">
                View proposal <ArrowRight className="h-3 w-3" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
