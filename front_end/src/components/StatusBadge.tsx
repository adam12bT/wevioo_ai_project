import type { JobStatus, StageStatus } from '@/types';

const STATUS_STYLES: Record<string, string> = {
  // Job statuses
  queued: 'bg-slate-100 text-slate-700 border-slate-300',
  submitting: 'bg-blue-50 text-blue-700 border-blue-300',
  running: 'bg-blue-50 text-blue-700 border-blue-300',
  evaluating: 'bg-teal-50 text-teal-700 border-teal-300',
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  failed: 'bg-rose-50 text-rose-700 border-rose-300',
  blocked: 'bg-amber-50 text-amber-700 border-amber-300',
  cancelled: 'bg-slate-100 text-slate-500 border-slate-300',
  // Stage statuses
  waiting: 'bg-slate-100 text-slate-600 border-slate-300',
  active: 'bg-blue-50 text-blue-700 border-blue-300',
  warning: 'bg-amber-50 text-amber-700 border-amber-300',
  // Generation section statuses
  generating: 'bg-blue-50 text-blue-700 border-blue-300',
  incomplete: 'bg-amber-50 text-amber-700 border-amber-300',
  // Quality/security
  pass: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  'human_review': 'bg-amber-50 text-amber-700 border-amber-300',
  healthy: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  unhealthy: 'bg-rose-50 text-rose-700 border-rose-300',
  degraded: 'bg-amber-50 text-amber-700 border-amber-300',
  unknown: 'bg-slate-100 text-slate-500 border-slate-300',
};

interface StatusBadgeProps {
  status: string;
  label?: string;
  size?: 'sm' | 'md';
  pulse?: boolean;
}

export function StatusBadge({ status, label, size = 'sm', pulse = false }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const style = STATUS_STYLES[normalized] || 'bg-slate-100 text-slate-700 border-slate-300';
  const display = label || status.replace(/_/g, ' ');
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium capitalize ${style} ${sizeClass}`}
    >
      {pulse && (
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-current animate-pulse-soft" />
      )}
      {display}
    </span>
  );
}

export function JobStatusBadge({ status, size = 'sm' }: { status: JobStatus; size?: 'sm' | 'md' }) {
  const isRunning = status === 'running' || status === 'submitting' || status === 'evaluating';
  return <StatusBadge status={status} size={size} pulse={isRunning} />;
}

export function StageStatusBadge({ status }: { status: StageStatus }) {
  return <StatusBadge status={status} />;
}
