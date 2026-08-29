import { Check, Loader2, AlertTriangle, XCircle, Clock, PauseCircle, Circle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { PipelineStage, StageStatus } from '@/types';
import { PIPELINE_STAGES } from '@/api/normalize';
import { StatusBadge } from './StatusBadge';

const STAGE_ICONS: Record<StageStatus, LucideIcon> = {
  waiting: Clock,
  active: Loader2,
  completed: Check,
  warning: AlertTriangle,
  failed: XCircle,
  blocked: PauseCircle,
};

export function PipelineTimeline({ stages }: { stages: PipelineStage[] }) {
  // If no stages provided, build from the canonical list
  const list: PipelineStage[] =
    stages.length > 0
      ? stages
      : PIPELINE_STAGES.map((s) => ({ name: s.key, status: 'waiting', label: s.label }));

  return (
    <ol className="relative space-y-0">
      {list.map((stage, idx) => {
        const status: StageStatus = stage.status || 'waiting';
        const Icon = STAGE_ICONS[status] || Circle;
        const isLast = idx === list.length - 1;
        const lineColor =
          status === 'completed'
            ? 'bg-emerald-400'
            : status === 'failed'
              ? 'bg-rose-400'
              : status === 'blocked'
                ? 'bg-amber-400'
                : 'bg-slate-200';

        return (
          <li key={stage.name + idx} className="relative flex gap-3 pb-6 last:pb-0">
            {!isLast && (
              <div
                className={`absolute left-4 top-8 bottom-0 w-0.5 ${lineColor}`}
                aria-hidden
              />
            )}
            <div className="relative z-10 flex-shrink-0">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full border-2 ${getStageCircleClass(status)}`}
              >
                <Icon
                  className={`h-4 w-4 ${status === 'active' ? 'animate-spin' : ''}`}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1 pt-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-800">
                  {stage.label || PIPELINE_STAGES.find((s) => s.key === stage.name)?.label || stage.name}
                </span>
                <StatusBadge status={status} />
              </div>
              {stage.message && (
                <p className="text-xs text-slate-500">{stage.message}</p>
              )}
              {stage.started_at && (
                <p className="text-xs text-slate-400">Started: {new Date(stage.started_at).toLocaleTimeString()}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function getStageCircleClass(status: StageStatus): string {
  switch (status) {
    case 'completed':
      return 'bg-emerald-50 border-emerald-400 text-emerald-600';
    case 'active':
      return 'bg-blue-50 border-blue-400 text-blue-600';
    case 'failed':
      return 'bg-rose-50 border-rose-400 text-rose-600';
    case 'blocked':
      return 'bg-amber-50 border-amber-400 text-amber-600';
    case 'warning':
      return 'bg-amber-50 border-amber-400 text-amber-600';
    default:
      return 'bg-slate-50 border-slate-200 text-slate-400';
  }
}
