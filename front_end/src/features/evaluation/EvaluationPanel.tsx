import { BarChart3, FileCheck, Gauge, Cpu } from 'lucide-react';
import type { Evaluation } from '@/types';
import { ScoreBar } from '@/components/ScoreBar';
import { EmptyState } from '@/components/EmptyState';
import { formatDuration, formatNumber, formatPercent } from '@/api/normalize';

export function EvaluationPanel({ evaluation }: { evaluation?: Evaluation }) {
  if (!evaluation || Object.keys(evaluation).length === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No evaluation data yet"
        description="RAG, output quality, and performance metrics will appear here once the evaluation stage completes."
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* RAG Quality */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <Gauge className="h-5 w-5 text-teal-500" />
          <h4 className="text-sm font-semibold text-slate-800">RAG Quality</h4>
          {evaluation.rag?.evaluation_mode && (
            <span className="ml-auto rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700">
              {evaluation.rag.evaluation_mode === 'automatic_proxy'
                ? 'Automatic proxy'
                : 'Labelled ground truth'}
            </span>
          )}
        </div>
        <div className="space-y-3">
          <ScoreBar
            value={evaluation.rag?.precision}
            label={evaluation.rag?.evaluation_mode === 'automatic_proxy' ? 'Candidate Precision Proxy' : 'Precision'}
          />
          <ScoreBar
            value={evaluation.rag?.recall}
            label={evaluation.rag?.evaluation_mode === 'automatic_proxy' ? 'Candidate Recall Proxy' : 'Recall'}
          />
          <ScoreBar value={evaluation.rag?.f1} label="F1 Score" />
          <ScoreBar value={evaluation.rag?.context_relevance} label="Context Relevance" />
          <ScoreBar value={evaluation.rag?.context_utilization} label="Context Utilization" />
          {evaluation.rag?.method && (
            <p className="rounded-lg bg-slate-50 p-2 text-xs leading-relaxed text-slate-500">
              {evaluation.rag.method}
            </p>
          )}
          <div className="grid grid-cols-2 gap-3 pt-2 text-sm sm:grid-cols-4">
            <div>
              <span className="text-slate-500">Candidate chunks: </span>
              <span className="font-semibold text-slate-800">{formatNumber(evaluation.rag?.candidate_chunks)}</span>
            </div>
            <div>
              <span className="text-slate-500">Chunks used: </span>
              <span className="font-semibold text-slate-800">{formatNumber(evaluation.rag?.used_chunks)}</span>
            </div>
            <div>
              <span className="text-slate-500">Relevant chunks: </span>
              <span className="font-semibold text-slate-800">{formatNumber(evaluation.rag?.relevant_chunks)}</span>
            </div>
            <div>
              <span className="text-slate-500">Retrieved chunks: </span>
              <span className="font-semibold text-slate-800">{formatNumber(evaluation.rag?.retrieved_chunks)}</span>
            </div>
          </div>
        </div>
        {evaluation.rag?.query_results && evaluation.rag.query_results.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <p className="text-xs font-semibold text-slate-600 mb-2">Query-level results</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-100">
                    <th className="py-1.5 pr-3">Query</th>
                    <th className="py-1.5 pr-3">Precision</th>
                    <th className="py-1.5 pr-3">Recall</th>
                    <th className="py-1.5 pr-3">Relevance</th>
                    <th className="py-1.5 pr-3">Utilization</th>
                    <th className="py-1.5">Used / candidates</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluation.rag.query_results.map((qr, i) => (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-1.5 pr-3 max-w-xs truncate text-slate-700">{qr.query || '—'}</td>
                      <td className="py-1.5 pr-3">{formatPercent(qr.precision)}</td>
                      <td className="py-1.5 pr-3">{formatPercent(qr.recall)}</td>
                      <td className="py-1.5 pr-3">{formatPercent(qr.context_relevance)}</td>
                      <td className="py-1.5 pr-3">{formatPercent(qr.context_utilization)}</td>
                      <td className="py-1.5 text-slate-600">{qr.used_chunks ?? '—'}/{qr.candidate_chunks ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Output Quality */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileCheck className="h-5 w-5 text-blue-500" />
          <h4 className="text-sm font-semibold text-slate-800">Output Quality</h4>
        </div>
        <div className="space-y-3">
          <ScoreBar value={evaluation.output_quality?.template_compliance} label="Template Compliance" />
          <ScoreBar value={evaluation.output_quality?.section_coverage} label="Section Coverage" />
          <ScoreBar value={evaluation.output_quality?.coherence} label="Coherence" />
          <ScoreBar value={evaluation.output_quality?.groundedness} label="Groundedness" />
          <ScoreBar value={evaluation.output_quality?.hallucination_rate} label="Hallucination Rate" />
          <ScoreBar value={evaluation.output_quality?.security_evaluation} label="Security Evaluation" />
          <div className="border-t border-slate-100 pt-2">
            <ScoreBar value={evaluation.output_quality?.overall_score} label="Overall Score" />
          </div>
        </div>
      </div>

      {/* Performance */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <Cpu className="h-5 w-5 text-slate-600" />
          <h4 className="text-sm font-semibold text-slate-800">Performance</h4>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="Total duration" value={formatDuration(evaluation.performance?.total_duration)} />
          <Metric label="Generation duration" value={formatDuration(evaluation.performance?.generation_duration)} />
          <Metric label="Pipeline throughput" value={evaluation.performance?.pipeline_throughput_per_hour != null ? `${evaluation.performance.pipeline_throughput_per_hour}/hr` : 'Not measured'} />
          <Metric label="LLM requests" value={formatNumber(evaluation.performance?.llm_request_count)} />
          <Metric label="Input tokens" value={formatNumber(evaluation.performance?.input_tokens)} />
          <Metric label="Output tokens" value={formatNumber(evaluation.performance?.output_tokens)} />
          <Metric label="Total tokens" value={formatNumber(evaluation.performance?.total_tokens)} />
        </div>

        {evaluation.performance?.duration_per_agent && evaluation.performance.duration_per_agent.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <p className="text-xs font-semibold text-slate-600 mb-2">Duration per agent</p>
            <div className="space-y-1.5">
              {evaluation.performance.duration_per_agent.map((a, i) => (
                <div key={i} className="flex justify-between text-xs">
                  <span className="text-slate-600">{a.agent || 'Unknown'}</span>
                  <span className="font-medium text-slate-800">{formatDuration(a.duration)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {evaluation.performance?.model_breakdown && evaluation.performance.model_breakdown.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <p className="text-xs font-semibold text-slate-600 mb-2">Model & provider breakdown</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-100">
                    <th className="py-1.5 pr-3">Model</th>
                    <th className="py-1.5 pr-3">Provider</th>
                    <th className="py-1.5 pr-3">Requests</th>
                    <th className="py-1.5 pr-3">Input</th>
                    <th className="py-1.5 pr-3">Output</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluation.performance.model_breakdown.map((m, i) => (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-1.5 pr-3 text-slate-700">{m.model || '—'}</td>
                      <td className="py-1.5 pr-3 text-slate-600">{m.provider || '—'}</td>
                      <td className="py-1.5 pr-3">{formatNumber(m.requests)}</td>
                      <td className="py-1.5 pr-3">{formatNumber(m.input_tokens)}</td>
                      <td className="py-1.5 pr-3">{formatNumber(m.output_tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}
