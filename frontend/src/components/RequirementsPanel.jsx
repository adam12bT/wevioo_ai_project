function Field({ label, children }) {
  return (
    <div className="field">
      <div className="field__label">{label}</div>
      <div className="field__value">{children}</div>
    </div>
  );
}

function ListOrDash({ items }) {
  if (!items || items.length === 0) return <span className="dash">—</span>;
  return (
    <ul className="chip-list">
      {items.map((item, i) => (
        <li key={i} className="chip">
          {item}
        </li>
      ))}
    </ul>
  );
}

export default function RequirementsPanel({ requirements, isLoading }) {
  if (isLoading) {
    return (
      <section className="sheet">
        <div className="sheet__tab">
          <span className="sheet__tab-index">01</span>
          <span className="eyebrow">Extraction</span>
        </div>
        <div className="sheet__body">
          <h2 style={{ marginBottom: 14 }}>Reading the tender…</h2>
          <SkeletonLines />
        </div>
      </section>
    );
  }

  if (!requirements || Object.keys(requirements).length === 0) {
    return null;
  }

  if (requirements.parse_error) {
    return (
      <section className="sheet sheet--alert">
        <div className="sheet__tab">
          <span className="sheet__tab-index">01</span>
          <span className="eyebrow">Extraction</span>
        </div>
        <div className="sheet__body">
          <div className="sheet__header">
            <h2>Couldn't parse a clean answer</h2>
          </div>
          <p className="sheet__lede">
            The model's raw response wasn't valid JSON. Here it is unparsed so nothing is lost:
          </p>
          <pre className="raw-block scrollbar-thin">{requirements.raw_response}</pre>
        </div>
      </section>
    );
  }

  const deadlines = requirements.deadlines || {};

  return (
    <section className="sheet">
      <div className="sheet__tab">
        <span className="sheet__tab-index">01</span>
        <span className="eyebrow">Extraction</span>
      </div>
      <div className="sheet__body">
        <div className="sheet__header">
          <h2>Requirements</h2>
        </div>

        <div style={{ marginTop: 14 }}>
          <Field label="Scope">
            <p style={{ margin: 0 }}>{requirements.scope_summary || <span className="dash">—</span>}</p>
          </Field>
        </div>

        <div className="field-grid">
          <Field label="Submission deadline">
            {deadlines.submission_deadline || <span className="dash">—</span>}
          </Field>
          <Field label="Project duration">
            {deadlines.project_duration || <span className="dash">—</span>}
          </Field>
          <Field label="Budget">{requirements.budget || <span className="dash">—</span>}</Field>
          <Field label="Selection method">
            {requirements.selection_method || <span className="dash">—</span>}
          </Field>
        </div>

        <Field label="Deliverables">
          <ListOrDash items={requirements.deliverables} />
        </Field>

        <Field label="Evaluation criteria">
          <ListOrDash items={requirements.evaluation_criteria} />
        </Field>
      </div>
    </section>
  );
}

function SkeletonLines() {
  return (
    <div className="skeleton-block">
      <div className="skeleton-line" style={{ width: "80%" }} />
      <div className="skeleton-line" style={{ width: "60%" }} />
      <div className="skeleton-line" style={{ width: "70%" }} />
    </div>
  );
}