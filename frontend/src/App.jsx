import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import RunList from "./components/RunList.jsx";
import PipelineRail from "./components/PipelineRail.jsx";
import StatusBadge from "./components/StatusBadge.jsx";
import VerificationPanel from "./components/VerificationPanel.jsx";
import RequirementsPanel from "./components/RequirementsPanel.jsx";
import ResearchPanel from "./components/ResearchPanel.jsx";
import ProposalPanel from "./components/ProposalPanel.jsx";
import QualityPanel from "./components/QualityPanel.jsx";
import KnowledgeBase from "./components/KnowledgeBase.jsx";
import UploadDropzone from "./components/UploadDropzone.jsx";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export default function App() {
  const [view, setView] = useState("pipeline"); // "pipeline" | "knowledge"
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const pollRef = useRef(null);

  // Poll the run list continuously (cheap) so new/other runs' status stays fresh.
  useEffect(() => {
    const refreshList = () => api.listRuns().then(setRuns).catch(() => {});
    refreshList();
    const id = setInterval(refreshList, 4000);
    return () => clearInterval(id);
  }, []);

  // Poll the selected run's full detail — fast while active, stop once terminal.
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (!selectedRunId) {
      setRunDetail(null);
      return;
    }

    const fetchDetail = () => {
      api
        .getRun(selectedRunId)
        .then((detail) => {
          setRunDetail(detail);
          if (!ACTIVE_STATUSES.has(detail.run_status) && pollRef.current) {
            clearInterval(pollRef.current);
          }
        })
        .catch(() => {});
    };

    fetchDetail();
    pollRef.current = setInterval(fetchDetail, 1500);
    return () => clearInterval(pollRef.current);
  }, [selectedRunId]);

  const handleUploadFile = async (file) => {
    setUploading(true);
    setUploadError(null);
    try {
      const { run_id } = await api.startRun(file);
      setShowUploadModal(false);
      setSelectedRunId(run_id);
      setView("pipeline");
      api.listRuns().then(setRuns).catch(() => {});
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const state = runDetail?.state || {};
  const isRunActive = ACTIVE_STATUSES.has(runDetail?.run_status);
  const currentStage = runDetail?.current_stage;

  return (
    <div className="app-shell">
      <div className="top-bar">
        <div className="top-bar__brand">
          <span className="top-bar__mark">§</span>
          Tender Desk
        </div>
        <nav className="top-bar__nav">
          <button
            className={`top-bar__tab ${view === "pipeline" ? "top-bar__tab--active" : ""}`}
            onClick={() => setView("pipeline")}
          >
            Pipeline
          </button>
          <button
            className={`top-bar__tab ${view === "knowledge" ? "top-bar__tab--active" : ""}`}
            onClick={() => setView("knowledge")}
          >
            Knowledge base
          </button>
        </nav>
      </div>

      <div className="app-body">
        {view === "pipeline" ? (
          <>
            <RunList
              runs={runs}
              selectedRunId={selectedRunId}
              onSelect={setSelectedRunId}
              onNewRun={() => setShowUploadModal(true)}
              uploading={uploading}
            />

            <div className="workspace">
              {selectedRunId ? (
                <>
                  <PipelineRail record={runDetail} />
                  <div className="sheets scrollbar-thin">
                    <div className="sheets__header">
                      <div>
                        <div className="eyebrow">{runDetail?.tender_filename}</div>
                        <h1 className="sheets__title">
                          {isRunActive
                            ? `Running — ${currentStage || "starting"}…`
                            : "Run summary"}
                        </h1>
                      </div>
                      <StatusBadge status={runDetail?.run_status} />
                    </div>

                    {runDetail?.error && (
                      <div className="banner banner--alert" style={{ width: "100%", maxWidth: "var(--doc-width)", marginBottom: 18 }}>
                        {runDetail.error}
                      </div>
                    )}

                    {runDetail?.run_status === "blocked" && (
                      <VerificationPanel errors={state.verification_errors} />
                    )}

                    {runDetail?.run_status !== "blocked" && (
                      <>
                        <RequirementsPanel
                          requirements={state.requirements}
                          isLoading={isRunActive && currentStage === "extraction"}
                        />
                        <ResearchPanel
                          researchSummary={state.research_summary}
                          isLoading={isRunActive && currentStage === "research"}
                          isActive={currentStage === "research" && isRunActive}
                        />
                        <ProposalPanel
                          draft={state.draft_proposal}
                          attempts={state.generation_attempts}
                          runId={selectedRunId}
                          isLoading={isRunActive && currentStage === "generation"}
                        />
                        <QualityPanel
                          report={state.quality_report}
                          passed={state.quality_passed}
                          runStatus={runDetail?.run_status}
                          isActive={isRunActive && currentStage === "quality"}
                        />
                      </>
                    )}
                  </div>
                </>
              ) : (
                <EmptyState onNewRun={() => setShowUploadModal(true)} />
              )}
            </div>
          </>
        ) : (
          <KnowledgeBase />
        )}
      </div>

      {showUploadModal && (
        <div className="modal-overlay" onClick={() => !uploading && setShowUploadModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal__header">
              <h2>Start a new tender run</h2>
              <button
                className="modal__close"
                onClick={() => setShowUploadModal(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <UploadDropzone
              onFile={handleUploadFile}
              disabled={uploading}
              label={uploading ? "Uploading & embedding…" : "Drop the tender PDF or DOCX here"}
              sublabel="Verifier will check it, then embed it into a fresh workspace"
            />
            {uploadError && <div className="banner banner--alert">{uploadError}</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({ onNewRun }) {
  return (
    <div className="empty-state">
      <div className="empty-state__mark">§</div>
      <h2>No tender selected</h2>
      <p>Pick a run from the list, or start a new one to send a tender through the pipeline.</p>
      <button className="btn btn--primary" onClick={onNewRun}>
        + New tender run
      </button>
    </div>
  );
}