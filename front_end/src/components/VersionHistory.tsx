import { History, Download, FileText } from 'lucide-react';
import type { DocumentVersion } from '@/types';
import { formatBytes, formatDateTime } from '@/api/normalize';
import { EmptyState } from '@/components/EmptyState';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { ErrorState } from '@/components/ErrorState';

interface VersionHistoryProps {
  versions: DocumentVersion[];
  loading: boolean;
  error: string | null;
  jobId: string;
  onDownload: (version: string | number) => Promise<void>;
  onRefresh: () => void;
}

export function VersionHistory({ versions, loading, error, onDownload, onRefresh }: VersionHistoryProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={onRefresh} />;
  }

  if (!versions || versions.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No versions available"
        description="Document versions will appear here once the versioning stage produces snapshots."
      />
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="border-b border-slate-100 px-4 py-3">
        <h4 className="text-sm font-semibold text-slate-800">Document Versions</h4>
        <p className="text-xs text-slate-500 mt-0.5">{versions.length} version(s) stored</p>
      </div>
      <ul className="divide-y divide-slate-100">
        {versions.map((v, i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100">
              <FileText className="h-4 w-4 text-slate-500" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-800">v{v.version}</span>
                {v.created_at && (
                  <span className="text-xs text-slate-400">{formatDateTime(v.created_at)}</span>
                )}
              </div>
              <div className="flex flex-wrap gap-3 mt-0.5 text-xs text-slate-500">
                {v.file_size != null && <span>{formatBytes(v.file_size)}</span>}
                {v.checksum && <span className="font-mono">SHA-256: {v.checksum.substring(0, 16)}…</span>}
              </div>
              {v.evaluation_summary && (
                <p className="mt-0.5 text-xs text-slate-600 truncate">{v.evaluation_summary}</p>
              )}
            </div>
            <button
              onClick={() => onDownload(v.version)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
