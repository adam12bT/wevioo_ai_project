import { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  FileText,
  BookOpen,
  Sparkles,
  PanelRightOpen,
  PanelRightClose,
  AlertTriangle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { GenerationProgress, GenerationSection, GenerationSectionStatus, Job } from '@/types';
import { normalizeGenerationProgress } from '@/api/normalize';
import { MarkdownDocument } from '@/components/MarkdownDocument';
import { StatusBadge } from '@/components/StatusBadge';
import { EmptyState } from '@/components/EmptyState';

interface GenerationWorkspaceProps {
  job: Job;
}

const SECTION_STATUS_ICONS: Record<GenerationSectionStatus, LucideIcon> = {
  waiting: Clock,
  generating: Loader2,
  complete: CheckCircle2,
  incomplete: AlertTriangle,
  failed: AlertCircle,
};

const MIN_SECTION_BODY_WORDS = 12;

function repairMojibake(value: string): string {
  const replacements: Record<string, string> = {
    'â€‘': '‑', 'â€“': '–', 'â€”': '—', 'â€™': '’', 'â€œ': '“', 'â€': '”',
    'â€¦': '…', 'â‰¤': '≤', 'â‰¥': '≥', 'â‚¬': '€', 'Ã€': 'À', 'Ã‰': 'É',
    'Ã©': 'é', 'Ã¨': 'è', 'Ãª': 'ê', 'Ã ': 'à', 'Ã§': 'ç', 'Â ': '\u00a0',
  };
  return Object.entries(replacements).reduce(
    (text, [broken, replacement]) => text.split(broken).join(replacement),
    value,
  );
}

function bodyWordCount(value: string): number {
  return value.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu)?.length || 0;
}

function cleanLiveSection(section: GenerationSection): GenerationSection {
  const lines = repairMojibake(section.content || '').split('\n');
  const firstHeading = lines[0]?.match(/^\s{0,3}#{1,6}\s+(.+)$/);
  if (firstHeading) lines.shift();

  // Old backend versions could append the next template heading to this card.
  const nextPeerHeading = lines.findIndex((line) => /^\s{0,3}#{1,2}\s+/.test(line));
  const content = (nextPeerHeading >= 0 ? lines.slice(0, nextPeerHeading) : lines)
    .join('\n')
    .trim();
  const status: GenerationSectionStatus = section.status === 'complete' && bodyWordCount(content) < MIN_SECTION_BODY_WORDS
    ? 'incomplete'
    : section.status;
  return { ...section, content, status };
}

/**
 * Splits a markdown document by headings and returns sections matching template structure.
 * Fallback when live generation progress is unavailable but draft_proposal exists.
 */
function splitMarkdownByHeadings(markdown: string): GenerationSection[] {
  const lines = repairMojibake(markdown).split('\n');
  const sections: GenerationSection[] = [];
  let currentTitle: string | null = null;
  let currentContent: string[] = [];

  const pushCurrent = () => {
    if (!currentTitle) return;
    const content = currentContent.join('\n').trim();
    sections.push({
      title: currentTitle,
      status: bodyWordCount(content) >= MIN_SECTION_BODY_WORDS ? 'complete' : 'incomplete',
      content,
    });
  };

  for (const line of lines) {
    const headingMatch = line.match(/^\s{0,3}(#{1,2})\s+(.+)$/);
    if (headingMatch) {
      pushCurrent();
      currentTitle = headingMatch[2].trim();
      currentContent = [];
    } else if (currentTitle) {
      currentContent.push(line);
    }
  }
  pushCurrent();

  // Prefer the most substantive occurrence when a malformed older draft
  // contains the same template heading more than once.
  const deduplicated = new Map<string, GenerationSection>();
  for (const section of sections) {
    const key = section.title.trim().toLocaleLowerCase();
    const previous = deduplicated.get(key);
    if (!previous || bodyWordCount(section.content || '') > bodyWordCount(previous.content || '')) {
      deduplicated.set(key, section);
    }
  }
  return [...deduplicated.values()];
}

export function GenerationWorkspace({ job }: GenerationWorkspaceProps) {
  const progress = normalizeGenerationProgress(job);
  const [followAI, setFollowAI] = useState(true);
  const [readingMode, setReadingMode] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const [activeSectionIdx, setActiveSectionIdx] = useState(0);
  const sectionRefs = useRef<(HTMLDivElement | null)[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // Live progress is best while generation is running. Once the upstream run
  // is terminal, the assembled draft is authoritative and may include repairs.
  const sections = useMemo<GenerationSection[]>(() => {
    const isTerminal = Boolean(
      job.status && ['completed', 'failed', 'blocked', 'warning'].includes(job.status),
    );
    if (isTerminal && job.draft_proposal) {
      return splitMarkdownByHeadings(job.draft_proposal);
    }
    if (progress?.sections && progress.sections.length > 0) {
      return progress.sections.map(cleanLiveSection);
    }
    if (job.draft_proposal) return splitMarkdownByHeadings(job.draft_proposal);
    return [];
  }, [progress, job.draft_proposal, job.status]);

  const hasLiveProgress = (progress?.sections?.length || 0) > 0;
  const completedCount = sections.filter((s) => s.status === 'complete').length;
  const totalCount = sections.length;
  const overallPct = progress?.overall_percent ?? (totalCount > 0 ? (completedCount / totalCount) * 100 : 0);
  const currentBatch = progress?.current_batch;
  const attempt = progress?.attempt;
  const generatingIdx = sections.findIndex((s) => s.status === 'generating');

  // Auto-follow the currently generating section
  useEffect(() => {
    if (!followAI || generatingIdx < 0) return;
    const el = sectionRefs.current[generatingIdx];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSectionIdx(generatingIdx);
    }
  }, [generatingIdx, followAI]);

  const handleOutlineClick = (idx: number) => {
    setActiveSectionIdx(idx);
    setFollowAI(false);
    sectionRefs.current[idx]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (sections.length === 0 && !job.draft_proposal) {
    return (
      <EmptyState
        icon={FileText}
        title="No generation data yet"
        description="The live proposal will appear here as the AI fills the selected proposal structure section by section."
      />
    );
  }

  const totalWords = sections.reduce((sum, s) => {
    return sum + (s.content ? s.content.split(/\s+/).filter(Boolean).length : 0);
  }, 0);

  return (
    <div className="space-y-4">
      {/* Top status bar */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-teal-500" />
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Live Proposal Generation</h3>
              <p className="text-xs text-slate-500">
                {hasLiveProgress
                  ? 'AI is filling the selected proposal structure in real time'
                  : 'Displaying completed draft proposal'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFollowAI(!followAI)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                followAI
                  ? 'bg-teal-50 text-teal-700 border border-teal-300'
                  : 'border border-slate-300 text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Follow AI: {followAI ? 'On' : 'Off'}
            </button>
            <button
              onClick={() => setReadingMode(!readingMode)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                readingMode ? 'bg-blue-50 text-blue-700 border border-blue-300' : 'border border-slate-300 text-slate-600 hover:bg-slate-50'
              }`}
            >
              <BookOpen className="h-3.5 w-3.5" />
              Reading mode
            </button>
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                showEvidence ? 'bg-slate-100 text-slate-700 border border-slate-300' : 'border border-slate-300 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {showEvidence ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
              Evidence
            </button>
          </div>
        </div>

        {/* Progress metrics */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Overall:</span>
            <span className="font-bold text-slate-800">{overallPct.toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Sections:</span>
            <span className="font-semibold text-slate-700">{completedCount}/{totalCount}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Words:</span>
            <span className="font-semibold text-slate-700">{totalWords.toLocaleString()}</span>
          </div>
          {currentBatch != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Batch:</span>
              <span className="font-semibold text-slate-700">{currentBatch}</span>
            </div>
          )}
          {attempt != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Attempt:</span>
              <span className="font-semibold text-slate-700">{attempt}</span>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-gradient-to-r from-teal-400 to-teal-500 transition-all duration-700"
            style={{ width: `${Math.min(100, overallPct)}%` }}
          />
        </div>
      </div>

      {/* Three-column workspace */}
      <div className="flex gap-4">
        {/* Left: section outline */}
        {!readingMode && (
          <nav className="hidden lg:block w-56 shrink-0">
            <div className="sticky top-0 rounded-xl border border-slate-200 bg-white p-3 max-h-[calc(100vh-200px)] overflow-y-auto">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2 px-1">Sections</p>
              <ul className="space-y-0.5">
                {sections.map((section, idx) => {
                  const Icon = SECTION_STATUS_ICONS[section.status] || Clock;
                  const isActive = idx === activeSectionIdx;
                  return (
                    <li key={idx}>
                      <button
                        onClick={() => handleOutlineClick(idx)}
                        className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors ${
                          isActive ? 'bg-teal-50 text-teal-700' : 'text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        <Icon
                          className={`h-3.5 w-3.5 shrink-0 ${section.status === 'generating' ? 'animate-spin' : ''} ${getStatusIconColor(section.status)}`}
                        />
                        <span className="truncate">{section.title || `Section ${idx + 1}`}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          </nav>
        )}

        {/* Center: live document */}
        <div
          ref={containerRef}
          className="flex-1 rounded-xl border border-slate-200 bg-white overflow-y-auto"
          style={{ maxHeight: 'calc(100vh - 240px)' }}
        >
          <div className="p-6 space-y-6">
            {sections.map((section, idx) => (
              <SectionView
                key={idx}
                section={section}
                idx={idx}
                ref={(el) => {
                  sectionRefs.current[idx] = el;
                }}
              />
            ))}
          </div>
        </div>

        {/* Right: evidence panel */}
        {!readingMode && showEvidence && (
          <aside className="hidden xl:block w-64 shrink-0">
            <div className="sticky top-0 rounded-xl border border-slate-200 bg-white p-3 max-h-[calc(100vh-200px)] overflow-y-auto">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2 px-1">
                Section Details
              </p>
              {activeSectionIdx < sections.length && (
                <SectionEvidence section={sections[activeSectionIdx]} />
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

function getStatusIconColor(status: GenerationSectionStatus): string {
  switch (status) {
    case 'complete':
      return 'text-emerald-500';
    case 'generating':
      return 'text-blue-500';
    case 'failed':
      return 'text-rose-500';
    case 'incomplete':
      return 'text-amber-500';
    default:
      return 'text-slate-400';
  }
}

interface SectionViewProps {
  section: GenerationSection;
  idx: number;
}

const SectionView = forwardRef<HTMLDivElement, SectionViewProps>(function SectionView(
  { section, idx },
  ref,
) {
  const Icon = SECTION_STATUS_ICONS[section.status] || Clock;
  const isGenerating = section.status === 'generating';
  const isFailed = section.status === 'failed';
  const isIncomplete = section.status === 'incomplete';

  return (
    <div
      ref={ref}
      className={`scroll-mt-4 rounded-lg p-4 transition-colors ${
        isGenerating ? 'border-2 border-blue-200 bg-blue-50/30' : 'border border-transparent'
      } ${isFailed ? 'border-rose-200 bg-rose-50/30' : ''} ${isIncomplete ? 'border-amber-200 bg-amber-50/20' : ''}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${section.status === 'generating' ? 'animate-spin' : ''} ${getStatusIconColor(section.status)}`} />
        <h3 className="text-sm font-semibold text-slate-800">
          {section.title || `Section ${idx + 1}`}
        </h3>
        <StatusBadge status={section.status} />
        {section.attempt && section.attempt > 1 && (
          <span className="text-xs text-slate-400">Attempt {section.attempt}</span>
        )}
      </div>

      {section.content ? (
        <MarkdownDocument content={section.content} />
      ) : isGenerating ? (
        <div className="space-y-2">
          <div className="skeleton h-4 w-full" />
          <div className="skeleton h-4" style={{ width: '95%' }} />
          <div className="skeleton h-4" style={{ width: '88%' }} />
          <div className="skeleton h-4" style={{ width: '92%' }} />
        </div>
      ) : section.error ? (
        <div className="flex items-start gap-2 rounded-lg bg-rose-50 p-3">
          <AlertCircle className="h-4 w-4 text-rose-500 shrink-0 mt-0.5" />
          <p className="text-sm text-rose-600">{section.error}</p>
        </div>
      ) : (
        <p className="text-sm text-slate-400 italic">Waiting for generation…</p>
      )}

      {section.content && section.content.includes('[À CONFIRMER') && (
        <div className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50 p-2.5 border border-amber-200">
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-700">
            This section contains items marked <span className="confirm-tag">[À CONFIRMER / TO BE CONFIRMED]</span> — verify against company knowledge base.
          </p>
        </div>
      )}
    </div>
  );
});

function SectionEvidence({ section }: { section: GenerationSection }) {
  if (!section) return <p className="text-xs text-slate-400 px-1">Select a section to view details.</p>;
  return (
    <div className="space-y-3 px-1">
      <div>
        <p className="text-xs font-medium text-slate-600 mb-1">Status</p>
        <StatusBadge status={section.status} />
      </div>
      {section.attempt != null && (
        <div>
          <p className="text-xs font-medium text-slate-600 mb-1">Attempt</p>
          <p className="text-sm text-slate-700">{section.attempt}</p>
        </div>
      )}
      {section.evidence && section.evidence.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-600 mb-1">Evidence</p>
          <ul className="space-y-1">
            {section.evidence.map((ev, i) => (
              <li key={i} className="text-xs text-slate-600 rounded bg-slate-50 p-1.5 border border-slate-100">
                {ev}
              </li>
            ))}
          </ul>
        </div>
      )}
      {section.error && (
        <div>
          <p className="text-xs font-medium text-rose-600 mb-1">Error</p>
          <p className="text-xs text-rose-600">{section.error}</p>
        </div>
      )}
      {section.content && (
        <div>
          <p className="text-xs font-medium text-slate-600 mb-1">Word count</p>
          <p className="text-sm text-slate-700">{section.content.split(/\s+/).filter(Boolean).length}</p>
        </div>
      )}
    </div>
  );
}

// Re-export type for convenience
export type { GenerationProgress };
