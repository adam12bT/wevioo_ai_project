import {
  Globe,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  ExternalLink,
  MinusCircle,
} from 'lucide-react';
import type { ResearchInfo } from '@/types';
import { StatusBadge } from '@/components/StatusBadge';
import { ScoreBar } from '@/components/ScoreBar';
import { MarkdownDocument } from '@/components/MarkdownDocument';
import { EmptyState } from '@/components/EmptyState';

export function ResearchPanel({ research }: { research?: ResearchInfo }) {
  if (!research || Object.keys(research).length === 0) {
    return (
      <EmptyState
        icon={Globe}
        title="No research data yet"
        description="Market research results will appear here once the research stage completes."
      />
    );
  }

  const skipped = research.skipped;
  const rejected = research.rejected;
  const accepted = research.accepted;

  return (
    <div className="space-y-4">
      {/* Status banner */}
      <div
        className={`rounded-xl border p-4 ${
          skipped
            ? 'border-slate-200 bg-slate-50'
            : rejected
              ? 'border-rose-200 bg-rose-50/50'
              : accepted
                ? 'border-emerald-200 bg-emerald-50/50'
                : 'border-blue-200 bg-blue-50/50'
        }`}
      >
        <div className="flex items-center gap-3">
          {skipped ? (
            <MinusCircle className="h-5 w-5 text-slate-400" />
          ) : rejected ? (
            <XCircle className="h-5 w-5 text-rose-500" />
          ) : accepted ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          ) : (
            <Globe className="h-5 w-5 text-blue-500" />
          )}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-slate-800">Research Status</h4>
              {research.status && <StatusBadge status={research.status} />}
            </div>
            {skipped && <p className="mt-0.5 text-xs text-slate-500">Research was intentionally skipped for this job.</p>}
            {rejected && (
              <p className="mt-0.5 text-xs text-rose-600">
                Research was rejected — relevance below threshold.
                {research.failure_reason && ` Reason: ${research.failure_reason}`}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Disclaimers */}
      <div className="flex items-start gap-2.5 rounded-lg border border-blue-200 bg-blue-50 p-3">
        <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
        <div className="text-xs text-blue-800 space-y-1">
          <p><strong>Market research provides external context only.</strong></p>
          <p>Research results are not proof of the bidding company's experience. Company references, CVs, and certifications must come from the knowledge base.</p>
        </div>
      </div>

      {/* Relevance score */}
      {!skipped && research.relevance_score != null && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
          <h4 className="text-sm font-semibold text-slate-700">Relevance Assessment</h4>
          <ScoreBar
            value={research.relevance_score}
            threshold={research.relevance_threshold}
            label="Relevance Score"
          />
          {research.relevance_threshold != null && (
            <p className="text-xs text-slate-500">
              Minimum relevance threshold: {(research.relevance_threshold * 100).toFixed(1)}%
            </p>
          )}
          {research.matched_keywords && research.matched_keywords.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1.5">Matched keywords</p>
              <div className="flex flex-wrap gap-1.5">
                {research.matched_keywords.map((kw, i) => (
                  <span key={i} className="rounded-full bg-teal-50 px-2 py-0.5 text-xs text-teal-700 border border-teal-200">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
          {research.relevance_explanation && (
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Relevance explanation</p>
              <p className="text-sm text-slate-600">{research.relevance_explanation}</p>
            </div>
          )}
        </div>
      )}

      {/* Research summary */}
      {research.summary && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-2">Research Summary</h4>
          <MarkdownDocument content={research.summary} />
        </div>
      )}

      {/* Sources */}
      {research.sources && research.sources.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-3">Sources</h4>
          <ul className="space-y-2">
            {research.sources.map((src, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <ExternalLink className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
                <div>
                  {src.url ? (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline font-medium"
                    >
                      {src.title || src.url}
                    </a>
                  ) : (
                    <span className="text-slate-700 font-medium">{src.title || 'Untitled source'}</span>
                  )}
                  {src.snippet && <p className="text-xs text-slate-500 mt-0.5">{src.snippet}</p>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {research.warnings && research.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <p className="text-xs font-semibold text-amber-700">Research Warnings</p>
          </div>
          <ul className="space-y-1">
            {research.warnings.map((w, i) => (
              <li key={i} className="text-xs text-amber-600">• {w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Failure reason */}
      {research.failure_reason && !rejected && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="h-4 w-4 text-rose-500" />
            <p className="text-xs font-semibold text-rose-700">Research Failure</p>
          </div>
          <p className="text-xs text-rose-600">{research.failure_reason}</p>
        </div>
      )}
    </div>
  );
}
