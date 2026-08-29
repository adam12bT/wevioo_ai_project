import { useCallback, useRef, useState } from 'react';
import { UploadCloud, FileText, X, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { formatBytes } from '@/api/normalize';

interface FileUploaderProps {
  label: string;
  description?: string;
  accept?: string;
  required?: boolean;
  file: File | null;
  error?: string | null;
  onFileSelected: (file: File | null) => void;
  onClearError?: () => void;
}

export function FileUploader({
  label,
  description,
  accept = '.pdf,.docx,.doc,.txt,.md',
  required = false,
  file,
  error,
  onFileSelected,
  onClearError,
}: FileUploaderProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      onFileSelected(files[0]);
    },
    [onFileSelected],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  const removeFile = useCallback(() => {
    onFileSelected(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [onFileSelected]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        <label className="text-sm font-semibold text-slate-700">{label}</label>
        {required && <span className="text-rose-500 text-sm">*</span>}
      </div>
      {description && <p className="text-xs text-slate-500">{description}</p>}

      {!file ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          role="button"
          tabIndex={0}
          className={`flex flex-col items-center justify-center cursor-pointer rounded-xl border-2 border-dashed py-8 px-4 text-center transition-colors ${
            dragging
              ? 'border-teal-400 bg-teal-50'
              : error
                ? 'border-rose-300 bg-rose-50/30'
                : 'border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100'
          }`}
        >
          <UploadCloud className={`mb-2 h-8 w-8 ${dragging ? 'text-teal-500' : 'text-slate-400'}`} />
          <p className="text-sm font-medium text-slate-600">Drag & drop or click to upload</p>
          <p className="mt-0.5 text-xs text-slate-400">{accept}</p>
        </div>
      ) : (
        <div className={`flex items-center gap-3 rounded-xl border p-3 ${error ? 'border-rose-300 bg-rose-50' : 'border-emerald-200 bg-emerald-50/50'}`}>
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${error ? 'bg-rose-100' : 'bg-emerald-100'}`}>
            {error ? <AlertCircle className="h-5 w-5 text-rose-500" /> : <CheckCircle2 className="h-5 w-5 text-emerald-500" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5 text-slate-400 shrink-0" />
              <p className="truncate text-sm font-medium text-slate-700">{file.name}</p>
            </div>
            <p className="text-xs text-slate-400">{formatBytes(file.size)} · {file.type || 'unknown type'}</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => inputRef.current?.click()}
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
              title="Replace file"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <button
              onClick={removeFile}
              className="rounded-md p-1.5 text-slate-400 hover:bg-rose-100 hover:text-rose-600"
              title="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-xs text-rose-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>{error}</span>
          {onClearError && (
            <button onClick={onClearError} className="ml-auto underline hover:text-rose-700">
              Dismiss
            </button>
          )}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files);
          if (onClearError) onClearError();
        }}
      />
    </div>
  );
}
