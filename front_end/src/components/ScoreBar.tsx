interface ScoreBarProps {
  value: number | null | undefined;
  threshold?: number | null;
  label?: string;
  showValue?: boolean;
  max?: number;
}

function getColor(pct: number, threshold?: number | null): string {
  if (threshold != null) {
    if (pct >= threshold) return 'bg-emerald-500';
    if (pct >= threshold * 0.8) return 'bg-amber-500';
    return 'bg-rose-500';
  }
  if (pct >= 80) return 'bg-emerald-500';
  if (pct >= 60) return 'bg-amber-500';
  return 'bg-rose-500';
}

export function ScoreBar({ value, threshold, label, showValue = true, max = 1 }: ScoreBarProps) {
  if (value == null || isNaN(value)) {
    return (
      <div className="space-y-1">
        {label && <div className="flex justify-between text-sm"><span className="text-slate-600">{label}</span></div>}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden" />
          <span className="text-xs text-slate-400 whitespace-nowrap">Not measured</span>
        </div>
      </div>
    );
  }

  const pct = Math.min(100, Math.max(0, max > 1 ? (value / max) * 100 : value * 100));
  const barColor = getColor(pct, threshold);
  const thresholdPct = threshold != null ? (max > 1 ? (threshold / max) * 100 : threshold * 100) : null;

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">{label}</span>
          {showValue && <span className="font-semibold text-slate-800">{pct.toFixed(1)}%</span>}
        </div>
      )}
      <div className="relative flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${barColor}`}
          style={{ width: `${pct}%` }}
        />
        {thresholdPct != null && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-slate-700 opacity-60"
            style={{ left: `${Math.min(100, thresholdPct)}%` }}
          />
        )}
      </div>
      {threshold != null && (
        <div className="text-xs text-slate-400">Threshold: {(max > 1 ? (threshold / max) * 100 : threshold * 100).toFixed(1)}%</div>
      )}
    </div>
  );
}
