import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api.js";

function countWords(text) {
  if (!text) return 0;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 1.5v8.3m0 0L4.6 6.4M8 9.8l3.4-3.4M2.5 12.5h11"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ProposalPanel({ draft, attempts, isLoading, runId }) {
  const wordCount = useMemo(() => countWords(draft), [draft]);

  if (!draft && !isLoading) return null;

  return (
    <section className="sheet sheet--proposal">
      <div className="sheet__tab">
        <span className="sheet__tab-index">03</span>
        <span className="eyebrow">Generation</span>
      </div>

      <div className="sheet__body">
        <div className="sheet__header sheet__header--row" style={{ padding: "0 24px" }}>
          <div>
            <h2>Draft technical proposal</h2>
          </div>
          <div className="sheet__header-actions">
            {attempts > 1 && <span className="pill">Attempt {attempts}</span>}
            {draft && !isLoading && (
              <span className="pill pill--muted">{wordCount.toLocaleString()} words</span>
            )}
            {draft && (
              <a className="btn btn--download" href={api.downloadUrl(runId)} download>
                <DownloadIcon />
                Download .md
              </a>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="skeleton-block" style={{ padding: "16px 24px 24px" }}>
            <p className="sheet__lede" style={{ margin: "0 0 12px" }}>
              Drafting the proposal using the tender requirements, research findings, and the
              company's past proposals, CVs, and project references…
            </p>
            <div className="skeleton-line" style={{ width: "95%" }} />
            <div className="skeleton-line" style={{ width: "88%" }} />
            <div className="skeleton-line" style={{ width: "92%" }} />
            <div className="skeleton-line" style={{ width: "60%" }} />
          </div>
        ) : (
          <div className="paper scrollbar-thin" style={{ marginTop: 14 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{draft}</ReactMarkdown>
          </div>
        )}
      </div>
    </section>
  );
}