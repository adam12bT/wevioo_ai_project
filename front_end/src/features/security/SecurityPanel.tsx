import { ShieldCheck, ShieldAlert, ShieldX, Info, FileWarning } from 'lucide-react';
import type { SecurityInfo, SecurityFinding } from '@/types';
import { StatusBadge } from '@/components/StatusBadge';
import { EmptyState } from '@/components/EmptyState';

export function SecurityPanel({ security }: { security?: SecurityInfo }) {
  if (!security || Object.keys(security).length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="No security data yet"
        description="Security scan results will appear here once the security stage completes."
      />
    );
  }

  const scanningPerformed = security.scanning_performed !== false;

  if (!scanningPerformed) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <Info className="h-5 w-5 text-slate-400 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-semibold text-slate-700">No automated security scan was performed.</h4>
          <p className="mt-0.5 text-xs text-slate-500">
            Security scanning was disabled for this job. Do not interpret this as a security pass.
          </p>
        </div>
      </div>
    );
  }

  const statusIcon = (() => {
    switch (security.status) {
      case 'pass':
        return <ShieldCheck className="h-5 w-5 text-emerald-500" />;
      case 'warning':
        return <FileWarning className="h-5 w-5 text-amber-500" />;
      case 'blocked':
        return <ShieldX className="h-5 w-5 text-rose-500" />;
      case 'human_review':
        return <ShieldAlert className="h-5 w-5 text-amber-500" />;
      default:
        return <ShieldCheck className="h-5 w-5 text-slate-400" />;
    }
  })();

  const statusBg = (() => {
    switch (security.status) {
      case 'pass':
        return 'border-emerald-200 bg-emerald-50/50';
      case 'warning':
      case 'human_review':
        return 'border-amber-200 bg-amber-50/50';
      case 'blocked':
        return 'border-rose-200 bg-rose-50/50';
      default:
        return 'border-slate-200 bg-white';
    }
  })();

  return (
    <div className="space-y-4">
      {/* Status banner */}
      <div className={`rounded-xl border p-4 ${statusBg}`}>
        <div className="flex items-center gap-3">
          {statusIcon}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-slate-800">Security Scan Result</h4>
              {security.status && <StatusBadge status={security.status} />}
            </div>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
              {security.scanner_mode && <span>Scanner: <strong>{security.scanner_mode}</strong></span>}
              {security.llm_guard_enabled != null && (
                <span>LLM Guard: <strong>{security.llm_guard_enabled ? 'Enabled' : 'Disabled'}</strong></span>
              )}
              {security.fallback_scanner_enabled != null && (
                <span>Fallback: <strong>{security.fallback_scanner_enabled ? 'Enabled' : 'Disabled'}</strong></span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Findings */}
      <div className="grid gap-3 sm:grid-cols-2">
        <FindingGroup title="PII Findings" findings={security.pii_findings} />
        <FindingGroup title="Email Findings" findings={security.email_findings} />
        <FindingGroup title="Phone Findings" findings={security.phone_findings} />
        <FindingGroup title="Secret / Credential Findings" findings={security.secret_findings} />
        <FindingGroup title="Malicious URL Findings" findings={security.malicious_url_findings} />
        <FindingGroup title="Prompt Injection Findings" findings={security.prompt_injection_findings} />
        <FindingGroup title="Toxicity Findings" findings={security.toxicity_findings} />
        <FindingGroup title="Refusal Findings" findings={security.refusal_findings} />
      </div>

      {/* Notes */}
      {security.notes && security.notes.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-2">Notes</h4>
          <ul className="space-y-1">
            {security.notes.map((note, i) => (
              <li key={i} className="text-sm text-slate-600">• {note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function FindingGroup({ title, findings }: { title: string; findings?: SecurityFinding[] }) {
  const hasFindings = findings && findings.length > 0;
  const total = findings?.reduce((sum, f) => sum + (f.count || 1), 0) || 0;

  return (
    <div className={`rounded-lg border p-3 ${hasFindings ? 'border-amber-200 bg-amber-50/30' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-center justify-between mb-2">
        <h5 className="text-xs font-semibold text-slate-700">{title}</h5>
        <span className={`text-xs font-medium ${hasFindings ? 'text-amber-600' : 'text-emerald-600'}`}>
          {hasFindings ? `${total} found` : 'None'}
        </span>
      </div>
      {hasFindings && (
        <ul className="space-y-1">
          {findings!.map((f, i) => (
            <li key={i} className="text-xs text-slate-600">
              <span className="font-medium">{f.type || f.severity || 'Finding'}</span>
              {f.count != null && ` (${f.count})`}
              {f.detail && `: ${f.detail}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
