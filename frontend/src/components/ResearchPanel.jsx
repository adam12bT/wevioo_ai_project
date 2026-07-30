import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function ResearchPanel({ researchSummary, isLoading, isActive }) {
  if (!researchSummary && !isLoading) return null;

  return (
    <section className="sheet">
      <div className="sheet__tab">
        <span className="sheet__tab-index">02</span>
        <span className="eyebrow">Research</span>
      </div>
      <div className="sheet__body">
        <div className="sheet__header">
          <h2>Market &amp; competitor scan</h2>
        </div>

        {isLoading || isActive ? (
          <div className="skeleton-block" style={{ marginTop: 12 }}>
            <p className="sheet__lede" style={{ margin: "0 0 12px" }}>
              Running autonomous web research on the market context for this tender — this can
              take a minute or two.
            </p>
            <div className="skeleton-line" style={{ width: "90%" }} />
            <div className="skeleton-line" style={{ width: "75%" }} />
            <div className="skeleton-line" style={{ width: "82%" }} />
          </div>
        ) : (
          <div className="markdown-block scrollbar-thin" style={{ marginTop: 12 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{researchSummary}</ReactMarkdown>
          </div>
        )}
      </div>
    </section>
  );
}