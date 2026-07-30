export default function VerificationPanel({ errors = [] }) {
  return (
    <section className="sheet sheet--alert">
      <div className="sheet__tab">
        <span className="sheet__tab-index">!</span>
        <span className="eyebrow">Verifier</span>
      </div>
      <div className="sheet__body">
        <div className="sheet__header">
          <h2>Blocked before processing</h2>
        </div>
        <p className="sheet__lede">
          This tender didn't pass the pre-flight checks, so no LLM calls were made. Fix the
          issue below and upload again.
        </p>
        <ul className="issue-list">
          {errors.map((err, i) => (
            <li key={i} className="issue-list__item">
              {err}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}