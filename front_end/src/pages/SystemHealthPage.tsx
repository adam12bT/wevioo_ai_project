import { HeartPulse, RefreshCw, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { useHealth } from '@/hooks/useHealth';
import { ErrorState } from '@/components/ErrorState';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import type { HealthComponent } from '@/types';

function StatusIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === 'healthy') return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
  if (s === 'unhealthy') return <XCircle className="h-5 w-5 text-rose-500" />;
  if (s === 'degraded') return <AlertCircle className="h-5 w-5 text-amber-500" />;
  return <AlertCircle className="h-5 w-5 text-slate-400" />;
}

function statusBorder(status: string): string {
  const s = status.toLowerCase();
  if (s === 'healthy') return 'border-emerald-200 bg-emerald-50/30';
  if (s === 'unhealthy') return 'border-rose-200 bg-rose-50/30';
  if (s === 'degraded') return 'border-amber-200 bg-amber-50/30';
  return 'border-slate-200 bg-white';
}

function ComponentCard({ label, component }: { label: string; component?: HealthComponent }) {
  const status = component?.status || 'unknown';
  return (
    <div className={`rounded-xl border p-4 ${statusBorder(status)}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-800">{label}</h3>
        <StatusIcon status={status} />
      </div>
      <div className="space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-slate-500">Status</span>
          <span className="font-medium capitalize text-slate-700">{status}</span>
        </div>
        {component?.provider && (
          <div className="flex justify-between">
            <span className="text-slate-500">Provider</span>
            <span className="font-medium text-slate-700">{component.provider}</span>
          </div>
        )}
        {component?.ready != null && (
          <div className="flex justify-between">
            <span className="text-slate-500">Ready</span>
            <span className={`font-medium ${component.ready ? 'text-emerald-600' : 'text-rose-600'}`}>
              {component.ready ? 'Yes' : 'No'}
            </span>
          </div>
        )}
        {component?.message && (
          <p className="mt-1.5 text-slate-500">{component.message}</p>
        )}
      </div>
    </div>
  );
}

export function SystemHealthPage() {
  const { health, loading, error, refresh } = useHealth(false);
  const healthErrors = health?.errors
    ? Array.isArray(health.errors)
      ? health.errors
      : Object.entries(health.errors).map(([component, message]) => `${component}: ${message}`)
    : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">System Health</h2>
          <p className="mt-1 text-sm text-slate-500">Real-time status of all pipeline components.</p>
        </div>
        <button
          onClick={refresh}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {loading && !health && <LoadingSkeleton lines={6} />}

      {error && !health && <ErrorState message={error} onRetry={refresh} />}

      {health && (
        <>
          {/* Overall status */}
          <div className={`rounded-xl border-2 p-5 ${statusBorder(health.status || 'unknown')}`}>
            <div className="flex items-center gap-3">
              <HeartPulse className="h-6 w-6 text-slate-600" />
              <div>
                <h3 className="text-base font-bold text-slate-900">Overall System Status</h3>
                <div className="flex items-center gap-2 mt-0.5">
                  <StatusIcon status={health.status || 'unknown'} />
                  <span className="text-sm font-semibold capitalize text-slate-700">{health.status || 'Unknown'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Component cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ComponentCard label="Redis" component={health.redis} />
            <ComponentCard label="Celery Queue" component={health.celery_queue} />
            <ComponentCard label="Agent Pipeline" component={health.agent_pipeline} />
            <ComponentCard label="Document Extractor" component={health.extractor} />
            <ComponentCard label="Database" component={health.database} />
            <ComponentCard label="Object Storage" component={health.storage} />
          </div>

          {/* Errors */}
          {healthErrors.length > 0 && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
              <h3 className="text-sm font-semibold text-rose-700 mb-2">Current Errors</h3>
              <ul className="space-y-1">
                {healthErrors.map((e, i) => (
                  <li key={i} className="text-sm text-rose-600">• {e}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
