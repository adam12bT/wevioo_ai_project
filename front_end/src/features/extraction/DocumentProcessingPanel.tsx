import { useState } from 'react';
import { FileText, ShieldCheck, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import type { DocumentProcessingInfo } from '@/types';
import { formatBytes, formatNumber } from '@/api/normalize';

interface DocumentProcessingPanelProps {
  tender?: DocumentProcessingInfo;
  template?: DocumentProcessingInfo;
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1.5 text-sm">
      <span className="text-slate-500 shrink-0">{label}</span>
      <span className="text-slate-800 font-medium text-right break-all">{value || '—'}</span>
    </div>
  );
}

function DocCard({ title, info }: { title: string; info?: DocumentProcessingInfo }) {
  const [expanded, setExpanded] = useState(false);
  if (!info) return null;

  const success = info.success !== false;

  return (
    <div className={`rounded-xl border p-4 ${success ? 'border-slate-200 bg-white' : 'border-rose-200 bg-rose-50/30'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {success ? (
            <ShieldCheck className="h-5 w-5 text-emerald-500" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-rose-500" />
          )}
          <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="rounded-md p-1 text-slate-400 hover:bg-slate-100"
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <FileText className="h-4 w-4 text-slate-400" />
        <span className="text-sm text-slate-700 truncate">{info.filename || 'Unknown file'}</span>
        {info.file_type && (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">{info.file_type}</span>
        )}
      </div>

      {success ? (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
          <ShieldCheck className="h-3 w-3" /> Processed successfully
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-600">
          <AlertTriangle className="h-3 w-3" /> Processing issues
        </span>
      )}

      {expanded && (
        <div className="mt-3 border-t border-slate-100 pt-3 space-y-0.5">
          <InfoRow label="File size" value={formatBytes(info.file_size)} />
          <InfoRow label="SHA-256" value={info.checksum ? info.checksum.substring(0, 16) + '…' : '—'} />
          <InfoRow label="Pages" value={formatNumber(info.page_count)} />
          <InfoRow label="Paragraphs" value={formatNumber(info.paragraph_count)} />
          <InfoRow label="Tables" value={formatNumber(info.table_count)} />
          <InfoRow label="Sections" value={formatNumber(info.section_count)} />
          <InfoRow label="Native pages" value={formatNumber(info.native_pages)} />
          <InfoRow label="OCR pages" value={formatNumber(info.ocr_pages)} />
          <InfoRow
            label="OCR confidence"
            value={info.ocr_confidence != null ? `${(info.ocr_confidence * 100).toFixed(1)}%` : '—'}
          />
          <InfoRow label="Indexed blocks" value={formatNumber(info.indexed_blocks)} />
          {info.anythingllm_workspace && (
            <InfoRow label="AnythingLLM workspace" value={info.anythingllm_workspace} />
          )}

          {info.extraction_warnings && info.extraction_warnings.length > 0 && (
            <div className="mt-2 rounded-lg bg-amber-50 p-2">
              <p className="text-xs font-semibold text-amber-700 mb-1">Extraction warnings</p>
              <ul className="space-y-0.5">
                {info.extraction_warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-600">• {w}</li>
                ))}
              </ul>
            </div>
          )}

          {info.indexing_errors && info.indexing_errors.length > 0 && (
            <div className="mt-2 rounded-lg bg-rose-50 p-2">
              <p className="text-xs font-semibold text-rose-700 mb-1">Indexing errors</p>
              <ul className="space-y-0.5">
                {info.indexing_errors.map((e, i) => (
                  <li key={i} className="text-xs text-rose-600">• {e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function DocumentProcessingPanel({ tender, template }: DocumentProcessingPanelProps) {
  if (!tender && !template) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <DocCard title="Tender Document" info={tender} />
      <DocCard title="Response Template" info={template} />
    </div>
  );
}
