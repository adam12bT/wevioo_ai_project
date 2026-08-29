import { CheckCircle2, AlertTriangle, XCircle, Info } from 'lucide-react';
import type { QualityInfo } from '@/types';
import { ScoreBar } from '@/components/ScoreBar';
import { StatusBadge } from '@/components/StatusBadge';
import { EmptyState } from '@/components/EmptyState';
import { formatNumber } from '@/api/normalize';

export function QualityPanel({ quality }: { quality?: QualityInfo }) {
  if (!quality || Object.keys(quality).length === 0) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="No quality data yet"
        description="Quality assessment results will appear here once the quality stage completes."
      />
    );
  }

  const statusIcon = (() => {
    switch (quality.status) {
      case 'pass':
      case 'passed':
        return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
      case 'warning':
        return <AlertTriangle className="h-5 w-5 text-amber-500" />;
      case 'fail':
      case 'failed':
        return <XCircle className="h-5 w-5 text-rose-500" />;
      default:
        return <Info className="h-5 w-5 text-slate-400" />;
    }
  })();

  return (
    <div className="space-y-4">
      {/* Status */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-3 mb-3">
          {statusIcon}
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-slate-800">Quality Assessment</h4>
            {quality.status && <StatusBadge status={quality.status} />}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="text-sm">
            <span className="text-slate-500">Word count: </span>
            <span className="font-semibold text-slate-800">{formatNumber(quality.word_count)}</span>
          </div>
          {quality.generation_attempt != null && (
            <div className="text-sm">
              <span className="text-slate-500">Generation attempt: </span>
              <span className="font-semibold text-slate-800">{quality.generation_attempt}</span>
            </div>
          )}
          {quality.max_attempts_reached != null && (
            <div className="text-sm">
              <span className="text-slate-500">Max attempts reached: </span>
              <span className={`font-semibold ${quality.max_attempts_reached ? 'text-rose-600' : 'text-slate-800'}`}>
                {quality.max_attempts_reached ? 'Yes' : 'No'}
              </span>
            </div>
          )}
          {quality.evaluator_available != null && (
            <div className="text-sm">
              <span className="text-slate-500">Evaluator available: </span>
              <span className={`font-semibold ${quality.evaluator_available ? 'text-emerald-600' : 'text-rose-600'}`}>
                {quality.evaluator_available ? 'Yes' : 'No'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Scores */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
        <h4 className="text-sm font-semibold text-slate-700">Quality Scores</h4>
        <ScoreBar value={quality.groundedness_score} threshold={quality.groundedness_threshold} label="Groundedness" />
        <ScoreBar value={quality.coherence_score} threshold={quality.coherence_threshold} label="Coherence" />

        <div className="flex items-start gap-2.5 rounded-lg bg-blue-50 border border-blue-200 p-3">
          <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
          <p className="text-xs text-blue-800">
            <strong>Important:</strong> A single unsupported claim or contradiction can cause the quality check to fail even when numerical scores pass.
          </p>
        </div>
      </div>

      {/* Section compliance */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <h4 className="text-sm font-semibold text-slate-700">Section Compliance</h4>
        <StringList title="Expected template sections" items={quality.required_sections} variant="neutral" />
        <StringList title="Generated sections" items={quality.present_sections} variant="neutral" />
        <StringList title="Passed sections" items={quality.passed_sections} variant="success" />
        <StringList title="Missing sections" items={quality.missing_sections} variant="warning" />
        <StringList title="Out-of-order sections" items={quality.out_of_order_sections} variant="warning" />
        <StringList title="Duplicate sections" items={quality.duplicate_sections} variant="warning" />
        <StringList title="Sections without substantive content" items={quality.incomplete_sections} variant="danger" />
        <StringList title="Failed sections" items={quality.failed_sections} variant="danger" />
      </div>

      {/* Non-blocking evidence gaps */}
      {quality.evidence_warnings && quality.evidence_warnings.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-amber-800">Supporting evidence required</h4>
              <p className="mt-1 text-xs text-amber-700">
                The placeholder itself is not a hallucination and does not lower groundedness. Missing CVs and
                supporting documents are still evaluated and must be supplied before submission; any unsupported
                claim about experience, personnel, or certification can still fail quality.
              </p>
              <ul className="mt-2 space-y-2">
                {quality.evidence_warnings.map((warning, index) => (
                  <li key={`${warning.section || 'evidence'}-${index}`} className="text-xs text-amber-800">
                    <span className="font-semibold">{warning.section || 'Proposal evidence'}</span>
                    {warning.placeholder_count != null && (
                      <span> ({warning.placeholder_count} placeholder{warning.placeholder_count === 1 ? '' : 's'})</span>
                    )}
                    {warning.message && <span>: {warning.message}</span>}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Issues */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <h4 className="text-sm font-semibold text-slate-700">Quality Issues</h4>
        <StringList title="Unsupported claims" items={quality.unsupported_claims} variant="danger" />
        <StringList title="Contradictions" items={quality.contradictions} variant="danger" />
        <StringList title="Coherence issues" items={quality.coherence_issues} variant="warning" />
      </div>

      {/* Evaluator errors */}
      {quality.evaluator_errors && quality.evaluator_errors.length > 0 && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
          <h5 className="text-sm font-semibold text-rose-700 mb-1.5">Evaluator Errors</h5>
          <ul className="space-y-1">
            {quality.evaluator_errors.map((e, i) => (
              <li key={i} className="text-xs text-rose-600">• {e}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Review notes */}
      {quality.review_notes && quality.review_notes.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <h5 className="text-sm font-semibold text-slate-700 mb-1.5">Review Notes</h5>
          <ul className="space-y-1">
            {quality.review_notes.map((n, i) => (
              <li key={i} className="text-xs text-slate-600">• {n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StringList({
  title,
  items,
  variant,
}: {
  title: string;
  items?: string[];
  variant: 'neutral' | 'success' | 'warning' | 'danger';
}) {
  if (!items || items.length === 0) return null;
  const colors = {
    neutral: 'border-slate-200 bg-white text-slate-700',
    success: 'border-emerald-200 bg-emerald-50/50 text-emerald-700',
    warning: 'border-amber-200 bg-amber-50/50 text-amber-700',
    danger: 'border-rose-200 bg-rose-50/50 text-rose-700',
  };
  return (
    <div className={`rounded-lg border p-3 ${colors[variant]}`}>
      <p className="text-xs font-semibold mb-1.5">{title} ({items.length})</p>
      <ul className="space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-xs">• {item}</li>
        ))}
      </ul>
    </div>
  );
}
