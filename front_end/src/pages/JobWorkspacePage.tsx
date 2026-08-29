import { useCallback, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  RotateCcw,
  XCircle,
  Clock,
  FileText,
  Layers,
  FileSearch,
  Globe,
  ShieldCheck,
  CheckCircle2,
  BarChart3,
  History,
  Loader2,
} from 'lucide-react';
import { useJob } from '@/hooks/useJob';
import { useJobEvents } from '@/hooks/useJobEvents';
import { useVersions } from '@/hooks/useVersions';
import { cancelJob, rerunJob, downloadProposal, downloadVersion, downloadBlob } from '@/api/client';
import {
  normalizePipelineStages,
  normalizeGenerationProgress,
  normalizeJob,
  formatDateTime,
  formatDuration,
  isTerminalStatus,
} from '@/api/normalize';
import { useToast } from '@/context/ToastContext';
import { PipelineTimeline } from '@/components/PipelineTimeline';
import { JobStatusBadge } from '@/components/StatusBadge';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { ErrorState } from '@/components/ErrorState';
import { ConfirmationModal } from '@/components/ConfirmationModal';
import { VersionHistory } from '@/components/VersionHistory';
import { DocumentProcessingPanel } from '@/features/extraction/DocumentProcessingPanel';
import { ExtractionPanel } from '@/features/extraction/ExtractionPanel';
import { ResearchPanel } from '@/features/research/ResearchPanel';
import { GenerationWorkspace } from '@/features/generation/GenerationWorkspace';
import { SecurityPanel } from '@/features/security/SecurityPanel';
import { QualityPanel } from '@/features/quality/QualityPanel';
import { EvaluationPanel } from '@/features/evaluation/EvaluationPanel';

type Tab =
  | 'pipeline'
  | 'processing'
  | 'extraction'
  | 'research'
  | 'generation'
  | 'security'
  | 'quality'
  | 'evaluation'
  | 'versions';

const TABS: { key: Tab; label: string; icon: typeof Clock }[] = [
  { key: 'pipeline', label: 'Pipeline', icon: Layers },
  { key: 'generation', label: 'Live Proposal', icon: FileText },
  { key: 'processing', label: 'Processing', icon: FileSearch },
  { key: 'extraction', label: 'Extraction', icon: FileSearch },
  { key: 'research', label: 'Research', icon: Globe },
  { key: 'security', label: 'Security', icon: ShieldCheck },
  { key: 'quality', label: 'Quality', icon: CheckCircle2 },
  { key: 'evaluation', label: 'Evaluation', icon: BarChart3 },
  { key: 'versions', label: 'Versions', icon: History },
];

export function JobWorkspacePage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { job, setJob, loading, error, refresh } = useJob(jobId);
  const { versions, loading: versionsLoading, error: versionsError, refresh: refreshVersions } = useVersions(jobId);
  const [activeTab, setActiveTab] = useState<Tab>('pipeline');
  const [showCancel, setShowCancel] = useState(false);
  const [showRerun, setShowRerun] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // SSE for real-time updates — merges into the same job state as polling
  const handleSSEUpdate = useCallback(
    (updated: typeof job) => {
      if (updated) {
        setJob((previous) =>
          normalizeJob({
            ...(previous || {}),
            ...updated,
            upstream_state: {
              ...(previous?.upstream_state || {}),
              ...(updated.upstream_state || {}),
            },
          }),
        );
      }
    },
    [setJob],
  );

  const handleSSETerminal = useCallback(() => {
    refresh();
  }, [refresh]);

  useJobEvents(jobId, handleSSEUpdate, handleSSETerminal);

  const stages = useMemo(() => (job ? normalizePipelineStages(job) : []), [job]);
  const progress = useMemo(() => (job ? normalizeGenerationProgress(job) : null), [job]);
  const isTerminal = job ? isTerminalStatus(job.status) : false;
  const canDownload = Boolean(
    job?.document_version || job?.result_path || job?.result_object_key,
  );

  const handleCancel = async () => {
    setShowCancel(false);
    if (!jobId) return;
    setActionLoading(true);
    try {
      await cancelJob(jobId);
      showToast('Job cancelled', 'success');
      refresh();
    } catch (err) {
      showToast('Failed to cancel job', 'error', err instanceof Error ? err.message : undefined);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRerun = async () => {
    setShowRerun(false);
    if (!jobId) return;
    setActionLoading(true);
    try {
      await rerunJob(jobId);
      showToast('Job rerun started', 'success');
      refresh();
    } catch (err) {
      showToast('Failed to rerun job', 'error', err instanceof Error ? err.message : undefined);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!jobId) return;
    setDownloading(true);
    try {
      const blob = await downloadProposal(jobId);
      const filename = job?.tender_filename?.replace(/\.[^.]+$/, '') || 'proposal';
      await downloadBlob(blob, `${filename}-proposal.md`);
      showToast('Proposal downloaded', 'success');
    } catch (err) {
      showToast('Download unavailable', 'error', err instanceof Error ? err.message : undefined);
    } finally {
      setDownloading(false);
    }
  };

  const handleVersionDownload = async (version: string | number) => {
    if (!jobId) return;
    try {
      const blob = await downloadVersion(jobId, version);
      await downloadBlob(blob, `proposal-v${version}.md`);
      showToast(`Version ${version} downloaded`, 'success');
    } catch (err) {
      showToast('Version download failed', 'error', err instanceof Error ? err.message : undefined);
    }
  };

  if (loading && !job) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton lines={2} />
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error && !job) {
    return <ErrorState title="Job not found" message={error} onRetry={refresh} />;
  }

  if (!job) return null;

  const overallPct = progress?.overall_percent ?? (stages.filter((s) => s.status === 'completed').length / Math.max(1, stages.length)) * 100;

  // Auto-switch to generation tab when generation is active
  const generatingStage = stages.find((s) => s.name === 'generation');
  if (generatingStage?.status === 'active' && activeTab === 'pipeline') {
    // Don't force-switch, just highlight
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/jobs')}
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-200"
          aria-label="Back to jobs"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-bold text-slate-900 truncate">{job.tender_filename || 'Untitled Job'}</h2>
            <JobStatusBadge status={job.status || 'queued'} size="md" />
          </div>
          <p className="text-xs text-slate-500 mt-0.5 font-mono">{job.job_id}</p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {!isTerminal && (
            <button
              onClick={() => setShowCancel(true)}
              disabled={actionLoading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose-300 px-3 py-1.5 text-sm font-medium text-rose-600 hover:bg-rose-50"
            >
              <XCircle className="h-4 w-4" />
              Cancel
            </button>
          )}
          <button
            onClick={() => setShowRerun(true)}
            disabled={actionLoading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            <RotateCcw className="h-4 w-4" />
            Rerun
          </button>
          {canDownload && (
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
            >
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Download
            </button>
          )}
        </div>
      </div>

      {/* Job metadata bar */}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6 rounded-xl border border-slate-200 bg-white p-4">
        <MetaItem label="Current Stage" value={stages.find((s) => s.status === 'active')?.name || job.current_stage || job.stage || '—'} />
        <MetaItem label="Created" value={formatDateTime(job.created_at)} />
        <MetaItem label="Updated" value={formatDateTime(job.updated_at)} />
        <MetaItem label="Duration" value={formatDuration(job.duration)} />
        <MetaItem label="Template" value={job.template_filename || 'Built-in default'} />
        <div className="space-y-0.5">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Progress</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
              <div className="h-full bg-teal-500 transition-all duration-700" style={{ width: `${Math.min(100, overallPct)}%` }} />
            </div>
            <span className="text-sm font-semibold text-slate-700">{overallPct.toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {job.status === 'failed' && (job.error || job.failure_reason) && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-rose-500" />
            <p className="text-sm font-semibold text-rose-700">Pipeline Failed</p>
          </div>
          <p className="mt-1 text-xs text-rose-600">{job.error || job.failure_reason}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-1 overflow-x-auto" aria-label="Job panels">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
                  activeTab === tab.key
                    ? 'border-teal-500 text-teal-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab content */}
      <div className="pb-8">
        {activeTab === 'pipeline' && (
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-4">Pipeline Timeline</h3>
            <PipelineTimeline stages={stages} />
          </div>
        )}

        {activeTab === 'processing' && (
          <DocumentProcessingPanel
            tender={job.document_processing?.tender}
            template={job.document_processing?.template}
          />
        )}

        {activeTab === 'extraction' && <ExtractionPanel extraction={job.extraction} />}

        {activeTab === 'research' && <ResearchPanel research={job.research} />}

        {activeTab === 'generation' && <GenerationWorkspace job={job} />}

        {activeTab === 'security' && <SecurityPanel security={job.security} />}

        {activeTab === 'quality' && <QualityPanel quality={job.quality} />}

        {activeTab === 'evaluation' && <EvaluationPanel evaluation={job.evaluation} />}

        {activeTab === 'versions' && (
          <VersionHistory
            versions={versions}
            loading={versionsLoading}
            error={versionsError}
            jobId={jobId || ''}
            onDownload={handleVersionDownload}
            onRefresh={refreshVersions}
          />
        )}
      </div>

      {/* Confirmation modals */}
      <ConfirmationModal
        open={showCancel}
        title="Cancel this job?"
        message="The pipeline will be stopped. This action cannot be undone."
        confirmLabel="Cancel Job"
        onConfirm={handleCancel}
        onCancel={() => setShowCancel(false)}
      />
      <ConfirmationModal
        open={showRerun}
        title="Rerun this job?"
        message="The pipeline will restart from the beginning. Previous versions are preserved."
        confirmLabel="Rerun"
        variant="info"
        onConfirm={handleRerun}
        onCancel={() => setShowRerun(false)}
      />
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="text-sm text-slate-800 truncate" title={value}>{value}</p>
    </div>
  );
}
