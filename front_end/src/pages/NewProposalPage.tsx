import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Rocket, ArrowRight, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';
import { FileUploader } from '@/components/FileUploader';
import { useToast } from '@/context/ToastContext';
import { createJob, ApiError } from '@/api/client';

const STEPS = ['Upload Tender', 'Response Structure', 'Evaluation Dataset', 'Review & Launch'] as const;

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export function NewProposalPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [step, setStep] = useState(0);
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [evalDataset, setEvalDataset] = useState<File | null>(null);
  const [tenderError, setTenderError] = useState<string | null>(null);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) return 'File exceeds 50MB maximum size.';
    return null;
  };

  const handleTenderSelected = (file: File | null) => {
    if (!file) {
      setTenderFile(null);
      return;
    }
    const err = validateFile(file);
    setTenderError(err);
    if (!err) setTenderFile(file);
  };

  const handleTemplateSelected = (file: File | null) => {
    if (!file) {
      setTemplateFile(null);
      return;
    }
    const err = validateFile(file);
    setTemplateError(err);
    if (!err) setTemplateFile(file);
  };

  const canProceed = () => {
    switch (step) {
      case 0:
        return tenderFile !== null && !tenderError;
      case 1:
        return !templateError;
      case 2:
        return true; // optional
      case 3:
        return tenderFile !== null;
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    if (!tenderFile) return;
    setSubmitting(true);
    try {
      const job = await createJob({
        file: tenderFile,
        template: templateFile || undefined,
        evaluation_dataset: evalDataset || undefined,
      });
      showToast('Job submitted successfully', 'success');
      const jobId = job.job_id || job.id;
      if (jobId) {
        navigate(`/jobs/${jobId}`);
      } else {
        navigate('/jobs');
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Failed to submit job';
      showToast('Submission failed', 'error', msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">New Proposal</h2>
        <p className="mt-1 text-sm text-slate-500">Upload a tender and optionally provide the client's response template.</p>
      </div>

      {/* Stepper */}
      <div className="mb-8 flex items-center gap-1">
        {STEPS.map((s, idx) => (
          <div key={s} className="flex items-center flex-1 last:flex-none">
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                idx < step
                  ? 'bg-emerald-500 text-white'
                  : idx === step
                    ? 'bg-teal-500 text-white'
                    : 'bg-slate-200 text-slate-400'
              }`}
            >
              {idx < step ? <CheckCircle2 className="h-4 w-4" /> : idx + 1}
            </div>
            <span className={`ml-2 text-xs font-medium hidden sm:inline ${idx <= step ? 'text-slate-700' : 'text-slate-400'}`}>{s}</span>
            {idx < STEPS.length - 1 && (
              <div className={`mx-2 h-0.5 flex-1 ${idx < step ? 'bg-emerald-400' : 'bg-slate-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-slate-800">Step 1: Upload Tender Document</h3>
              <p className="mt-1 text-sm text-slate-500">Upload the tender or RFP document you want to respond to.</p>
            </div>
            <FileUploader
              label="Tender Document"
              description="PDF, DOCX, or TXT file containing the tender requirements."
              required
              file={tenderFile}
              error={tenderError}
              onFileSelected={handleTenderSelected}
              onClearError={() => setTenderError(null)}
            />
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-slate-800">Step 2: Response Template (Optional)</h3>
              <p className="mt-1 text-sm text-slate-500">Upload the client's template when one exists. Otherwise, the pipeline uses its versioned general proposal structure.</p>
            </div>
            <FileUploader
              label="Response Template"
              description="Optional PDF or DOCX. Leave empty to use the built-in default template."
              file={templateFile}
              error={templateError}
              onFileSelected={handleTemplateSelected}
              onClearError={() => setTemplateError(null)}
            />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-slate-800">Step 3: Evaluation Dataset (Optional)</h3>
              <p className="mt-1 text-sm text-slate-500">Upload a dataset to evaluate RAG retrieval quality against ground truth.</p>
            </div>
            <FileUploader
              label="Evaluation Dataset"
              description="Optional — JSON or CSV file with expected retrieval results."
              file={evalDataset}
              onFileSelected={setEvalDataset}
            />
            {evalDataset && (
              <button
                onClick={() => setEvalDataset(null)}
                className="text-xs text-slate-500 underline hover:text-slate-700"
              >
                Skip evaluation dataset
              </button>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-semibold text-slate-800">Step 4: Review & Launch</h3>
              <p className="mt-1 text-sm text-slate-500">Confirm your files and submit to the pipeline.</p>
            </div>
            <div className="space-y-2 rounded-lg bg-slate-50 p-4">
              <ReviewRow label="Tender Document" file={tenderFile} required />
              <ReviewRow label="Response Template" file={templateFile} />
              <ReviewRow label="Evaluation Dataset" file={evalDataset} />
            </div>
            <div className="flex items-start gap-2.5 rounded-lg bg-teal-50 border border-teal-200 p-3">
              <Rocket className="h-4 w-4 text-teal-600 shrink-0 mt-0.5" />
              <p className="text-xs text-teal-800">
                Once launched, you'll be taken to the job workspace where you can follow the pipeline in real time.
              </p>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4">
          <button
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          {step < 3 ? (
            <button
              onClick={() => setStep(step + 1)}
              disabled={!canProceed()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting || !canProceed()}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  <Rocket className="h-4 w-4" />
                  Launch Pipeline
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ReviewRow({ label, file, required }: { label: string; file: File | null; required?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-600">
        {label}
        {required && <span className="text-rose-500 ml-1">*</span>}
      </span>
      {file ? (
        <span className="text-slate-800 font-medium truncate max-w-xs">{file.name}</span>
      ) : (
        <span className="text-slate-400 italic">Not provided</span>
      )}
    </div>
  );
}
