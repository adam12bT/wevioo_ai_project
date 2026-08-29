import { useState } from 'react';
import { ChevronDown, ChevronRight, FileSearch, Code2 } from 'lucide-react';
import type { TenderRequirements } from '@/types';
import { EmptyState } from '@/components/EmptyState';

export function ExtractionPanel({ extraction }: { extraction?: TenderRequirements }) {
  const [showRaw, setShowRaw] = useState(false);

  if (!extraction || Object.keys(extraction).length === 0) {
    return (
      <EmptyState
        icon={FileSearch}
        title="No extraction data yet"
        description="Tender requirements will appear here once the extraction stage completes."
      />
    );
  }

  const listFields: { key: keyof TenderRequirements; label: string }[] = [
    { key: 'deliverables', label: 'Deliverables' },
    { key: 'mandatory_requirements', label: 'Mandatory Requirements' },
    { key: 'technical_constraints', label: 'Technical Constraints' },
    { key: 'contractual_constraints', label: 'Contractual Constraints' },
    { key: 'domain_specific_constraints', label: 'Domain-specific Constraints' },
    { key: 'required_evidence', label: 'Required Evidence' },
    { key: 'required_forms', label: 'Required Forms and Schedules' },
    { key: 'additional_requirements', label: 'Additional Requirements' },
    { key: 'evaluation_criteria', label: 'Evaluation Criteria' },
    { key: 'response_template_rules', label: 'Response Template Rules' },
    { key: 'required_sections', label: 'Required Sections' },
    { key: 'required_section_order', label: 'Required Section Order' },
    { key: 'formatting_instructions', label: 'Formatting Instructions' },
  ];

  const scalarFields: { key: keyof TenderRequirements; label: string }[] = [
    { key: 'scope_summary', label: 'Scope Summary' },
    { key: 'budget', label: 'Budget' },
    { key: 'submission_deadline', label: 'Submission Deadline' },
    { key: 'project_duration', label: 'Project Duration' },
    { key: 'template_source', label: 'Template Source' },
    { key: 'template_version', label: 'Template Version' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-800">Extracted Tender Requirements</h3>
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          <Code2 className="h-3.5 w-3.5" />
          {showRaw ? 'Hide raw data' : 'View raw data'}
        </button>
      </div>

      {showRaw ? (
        <pre className="overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-200 max-h-96">
          {JSON.stringify(extraction, null, 2)}
        </pre>
      ) : (
        <>
          {/* Scalar fields as cards */}
          <div className="grid gap-3 sm:grid-cols-2">
            {scalarFields.map(({ key, label }) => {
              const value = extraction[key];
              if (!value) return null;
              return (
                <div key={key} className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-500 mb-1">{label}</p>
                  <p className="text-sm text-slate-800">{String(value)}</p>
                </div>
              );
            })}
          </div>

          {/* List fields as expandable groups */}
          <div className="space-y-2">
            {listFields.map(({ key, label }) => {
              const value = extraction[key];
              if (!value || !Array.isArray(value) || value.length === 0) return null;
              return <ExpandableList key={key} label={label} items={value as string[]} />;
            })}
          </div>
        </>
      )}
    </div>
  );
}

function ExpandableList({ label, items }: { label: string; items: string[] }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
      >
        <span>{label}</span>
        <span className="flex items-center gap-2">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{items.length}</span>
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>
      {open && (
        <ul className="border-t border-slate-100 px-4 py-2 space-y-1.5">
          {items.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-700">
              <span className="text-teal-500 shrink-0">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
