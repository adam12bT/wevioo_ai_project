import { useEffect, useState } from "react";
import { api } from "../api.js";
import UploadDropzone from "./UploadDropzone.jsx";

const CATEGORY_META = {
  past_proposals: {
    title: "Past proposals",
    hint: "Used for tone & structure reference when drafting.",
  },
  cvs: {
    title: "Consultant CVs",
    hint: "Used, and only used, to write the Proposed Team section.",
  },
  project_references: {
    title: "Project references",
    hint: "Used for the Why Us / track record section.",
  },
};

function CategoryCard({ category, data, onUpload, uploading }) {
  const meta = CATEGORY_META[category];
  return (
    <div className="kb-card">
      <div className="kb-card__header">
        <div>
          <h3>{meta.title}</h3>
          <p className="kb-card__hint">{meta.hint}</p>
        </div>
        <span className="pill">{data?.document_count ?? 0} docs</span>
      </div>

      <UploadDropzone
        compact
        disabled={uploading}
        label={uploading ? "Uploading…" : "Add PDF or DOCX"}
        sublabel={`→ workspace "${data?.slug || ""}"`}
        onFile={(file) => onUpload(category, file)}
      />

      {data?.documents?.length > 0 ? (
        <ul className="kb-doc-list scrollbar-thin">
          {data.documents.map((doc, i) => (
            <li key={doc.id || i}>{doc.title}</li>
          ))}
        </ul>
      ) : (
        <p className="kb-card__empty">
          {data?.exists === false
            ? "Workspace not created yet — it's created automatically on first upload."
            : "No documents indexed yet."}
        </p>
      )}
    </div>
  );
}

export default function KnowledgeBase() {
  const [status, setStatus] = useState(null);
  const [uploadingCategory, setUploadingCategory] = useState(null);
  const [error, setError] = useState(null);

  const refresh = () => {
    api
      .knowledgeStatus()
      .then(setStatus)
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, []);

  const handleUpload = async (category, file) => {
    setUploadingCategory(category);
    setError(null);
    try {
      await api.uploadKnowledgeFile(category, file);
      refresh();
    } catch (e) {
      setError(`Upload failed: ${e.message}`);
    } finally {
      setUploadingCategory(null);
    }
  };

  return (
    <div className="kb-page scrollbar-thin">
      <div className="kb-page__intro">
        <div className="eyebrow">Company knowledge base</div>
        <h1>Persistent context for every tender</h1>
        <p>
          These three workspaces stay populated across every run — separate from the one-off
          workspace created per tender. The Generation agent searches them for genuinely
          relevant past material instead of writing generic prose.
        </p>
      </div>

      {error && <div className="banner banner--alert">{error}</div>}

      <div className="kb-grid">
        {Object.keys(CATEGORY_META).map((category) => (
          <CategoryCard
            key={category}
            category={category}
            data={status?.[category]}
            onUpload={handleUpload}
            uploading={uploadingCategory === category}
          />
        ))}
      </div>
    </div>
  );
}
