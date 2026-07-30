export default function QualityPanel({ report, passed, runStatus, isActive }) {
  if (!report) {
    if (!isActive) return null;
    return (
      <section className="sheet">
        <div className="sheet__tab">
          <span className="sheet__tab-index">04</span>
          <span className="eyebrow">Quality &amp; security</span>
        </div>
        <div className="sheet__body">
          <div className="sheet__header">
            <h2>Checking the draft…</h2>
          </div>
          <div className="skeleton-block" style={{ marginTop: 12 }}>
            <div className="skeleton-line" style={{ width: "70%" }} />
            <div className="skeleton-line" style={{ width: "50%" }} />
          </div>
        </div>
      </section>
    );
  }

  const piiEntries = Object.entries(report.pii_findings || {});

  return (
    <section className={`sheet ${passed ? "" : "sheet--warn"}`}>
      <div className="sheet__tab">
        <span className="sheet__tab-index">04</span>
        <span className="eyebrow">Quality &amp; security</span>
      </div>
      <div className="sheet__body">
        <div className="sheet__header sheet__header--row">
          <div>
            <h2>{passed ? "Passed" : runStatus === "failed" ? "Failed — max retries hit" : "Needs another pass"}</h2>
          </div>
          <span className={`pill ${passed ? "pill--good" : "pill--warn"}`}>
            {report.word_count} words
          </span>
        </div>

        <div className="field-grid" style={{ marginTop: 14 }}>
          <div className="field">
            <div className="field__label">Template sections</div>
            <div className="field__value">
              {report.missing_sections?.length ? (
                <ul className="chip-list">
                  {report.missing_sections.map((s) => (
                    <li key={s} className="chip chip--warn">
                      missing: {s}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="chip chip--good">all present</span>
              )}
            </div>
          </div>

          <div className="field">
            <div className="field__label">Naive PII scan</div>
            <div className="field__value">
              {piiEntries.length ? (
                <ul className="chip-list">
                  {piiEntries.map(([label, count]) => (
                    <li key={label} className="chip chip--warn">
                      {label}: {count}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="chip chip--good">none found</span>
              )}
            </div>
          </div>
        </div>

        {report.notes?.length > 0 && (
          <div className="field">
            <div className="field__label">Notes</div>
            <ul className="issue-list">
              {report.notes.map((note, i) => (
                <li key={i} className="issue-list__item">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="sheet__footnote">
          This is a placeholder regex/length-based check — LLM Guard integration (PII,
          prompt-injection, hallucination scoring) is planned to replace it.
        </p>
      </div>
    </section>
  );
}