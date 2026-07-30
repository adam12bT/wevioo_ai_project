import StatusBadge from "./StatusBadge.jsx";

function timeAgo(unixSeconds) {
  const diff = Date.now() / 1000 - unixSeconds;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function RunList({ runs, selectedRunId, onSelect, onNewRun, uploading }) {
  return (
    <aside className="run-list">
      <div className="run-list__header">
        <div className="eyebrow">Tenders</div>
        <h1 className="run-list__title">Tender Desk</h1>
      </div>

      <button className="btn btn--primary run-list__new" onClick={onNewRun} disabled={uploading}>
        {uploading ? "Uploading…" : "+ New tender run"}
      </button>

      <div className="run-list__items scrollbar-thin">
        {runs.length === 0 && (
          <div className="run-list__empty">
            No tenders yet. Upload one to start the pipeline.
          </div>
        )}
        {runs.map((run) => (
          <button
            key={run.run_id}
            className={`run-item ${run.run_id === selectedRunId ? "run-item--active" : ""}`}
            onClick={() => onSelect(run.run_id)}
          >
            <div className="run-item__top">
              <span className="run-item__name" title={run.tender_filename}>
                {run.tender_filename}
              </span>
            </div>
            <div className="run-item__meta">
              <StatusBadge status={run.run_status} small />
              <span className="run-item__time">{timeAgo(run.created_at)}</span>
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
