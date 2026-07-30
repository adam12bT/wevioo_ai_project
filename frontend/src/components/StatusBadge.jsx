const STATUS_STYLES = {
  queued: { label: "Queued", tone: "slate" },
  running: { label: "Running", tone: "amber" },
  blocked: { label: "Blocked", tone: "rust" },
  failed: { label: "Failed", tone: "rust" },
  done: { label: "Done", tone: "teal" },
};

export default function StatusBadge({ status, small = false }) {
  const meta = STATUS_STYLES[status] || { label: status || "Unknown", tone: "slate" };
  return (
    <span className={`status-badge status-badge--${meta.tone} ${small ? "status-badge--sm" : ""}`}>
      <span className="status-badge__dot" />
      {meta.label}
    </span>
  );
}
