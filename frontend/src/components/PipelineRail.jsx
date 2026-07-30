const STAGES = [
  { key: "verifier", label: "Verify", hint: "File & format checks" },
  { key: "extraction", label: "Extract", hint: "Deliverables, deadlines, budget" },
  { key: "research", label: "Research", hint: "Market & competitor scan" },
  { key: "generation", label: "Generate", hint: "Draft technical proposal" },
  { key: "quality", label: "Quality", hint: "PII scan & template check" },
];

function stageStatus(stageKey, record) {
  if (!record) return "pending";

  const { current_stage, completed_stages = [], run_status } = record;
  const isCurrent = current_stage === stageKey;
  const hasRun = completed_stages.includes(stageKey);

  if (stageKey === "verifier" && run_status === "blocked") return "blocked";
  if (isCurrent && (run_status === "running" || run_status === "queued")) return "active";
  if (stageKey === "quality" && run_status === "failed" && hasRun) return "blocked";
  if (hasRun) return "done";
  return "pending";
}

export default function PipelineRail({ record }) {
  return (
    <nav className="docket" aria-label="Pipeline progress">
      <div className="docket__eyebrow eyebrow">Docket · pipeline</div>
      <ol className="docket__list">
        {STAGES.map((stage, i) => {
          const status = stageStatus(stage.key, record);
          const isLast = i === STAGES.length - 1;
          return (
            <li key={stage.key} className="docket__item">
              <div className="docket__stage">
                <div className={`docket__node docket__node--${status}`} title={stage.hint}>
                  {status === "done" ? "✓" : status === "blocked" ? "!" : i + 1}
                </div>
                <div className={`docket__label docket__label--${status}`}>{stage.label}</div>
              </div>
              {!isLast && (
                <div className={`docket__line ${status === "done" ? "docket__line--done" : ""}`} />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export { STAGES };