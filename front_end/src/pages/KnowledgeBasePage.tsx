import { useCallback, useRef, useState } from 'react';
import {
  Database,
  Upload,
  FileText,
  FolderKanban,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { useKnowledge } from '@/hooks/useKnowledge';
import { uploadKnowledgeDocument } from '@/api/client';
import { useToast } from '@/context/ToastContext';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { formatBytes, formatDateTime } from '@/api/normalize';

const CATEGORIES = [
  'cvs',
  'project_references',
  'past_proposals',
];

const CATEGORY_LABELS: Record<string, string> = {
  cvs: 'CVs',
  project_references: 'Project references',
  past_proposals: 'Past proposals',
};

interface UploadState {
  [key: string]: { loading: boolean; error: string | null };
}

export function KnowledgeBasePage() {
  const { documents, loading, error, refresh } = useKnowledge();
  const { showToast } = useToast();
  const [uploadStates, setUploadStates] = useState<UploadState>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const handleUpload = useCallback(
    async (category: string, file: File) => {
      setUploadStates((prev) => ({ ...prev, [category]: { loading: true, error: null } }));
      try {
        await uploadKnowledgeDocument(category, file);
        setUploadStates((prev) => ({ ...prev, [category]: { loading: false, error: null } }));
        showToast(`Uploaded to ${CATEGORY_LABELS[category]}`, 'success', file.name);
        refresh();
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        setUploadStates((prev) => ({ ...prev, [category]: { loading: false, error: msg } }));
        showToast('Upload failed', 'error', msg);
      }
    },
    [refresh, showToast],
  );

  const docsByCategory = CATEGORIES.reduce(
    (acc, cat) => {
      acc[cat] = documents.filter((d) => d.category === cat);
      return acc;
    },
    {} as Record<string, typeof documents>,
  );

  if (loading) {
    return <LoadingSkeleton lines={8} />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Knowledge Base</h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage company documents used for evidence in proposals. CVs, references, and certifications must come from here — not from research.
        </p>
      </div>

      {/* Category cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CATEGORIES.map((category) => {
          const catDocs = docsByCategory[category] || [];
          const uploadState = uploadStates[category];
          return (
            <div key={category} className="rounded-xl border border-slate-200 bg-white overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <div className="flex items-center gap-2">
                  <FolderKanban className="h-4 w-4 text-teal-500" />
                  <h3 className="text-sm font-semibold text-slate-800">{CATEGORY_LABELS[category]}</h3>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{catDocs.length}</span>
              </div>

              {/* Upload area */}
              <div className="border-b border-slate-100 p-3">
                <input
                  ref={(el) => {
                    fileInputRefs.current[category] = el;
                  }}
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleUpload(category, e.target.files[0]);
                    e.target.value = '';
                  }}
                />
                <button
                  onClick={() => fileInputRefs.current[category]?.click()}
                  disabled={uploadState?.loading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 py-2.5 text-xs font-medium text-slate-500 hover:border-teal-400 hover:text-teal-600 disabled:opacity-50"
                >
                  {uploadState?.loading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Uploading…
                    </>
                  ) : (
                    <>
                      <Upload className="h-3.5 w-3.5" />
                      Upload file
                    </>
                  )}
                </button>
                {uploadState?.error && (
                  <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-600">
                    <AlertCircle className="h-3 w-3" />
                    <span className="truncate">{uploadState.error}</span>
                  </div>
                )}
              </div>

              {/* Documents */}
              <div className="max-h-64 overflow-y-auto">
                {catDocs.length === 0 ? (
                  <p className="px-4 py-6 text-center text-xs text-slate-400">No documents yet</p>
                ) : (
                  <ul className="divide-y divide-slate-50">
                    {catDocs.map((doc) => (
                      <li key={doc.id} className="flex items-center gap-2 px-4 py-2 hover:bg-slate-50">
                        <FileText className="h-4 w-4 text-slate-400 shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium text-slate-700">{doc.name}</p>
                          <p className="text-xs text-slate-400">
                            {formatBytes(doc.size)} · {formatDateTime(doc.created_at)}
                          </p>
                        </div>
                        {doc.status === 'indexed' && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {documents.length === 0 && (
        <EmptyState
          icon={Database}
          title="Knowledge base is empty"
          description="Upload company documents to provide evidence for proposal generation."
        />
      )}

    </div>
  );
}
