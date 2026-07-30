import { useRef, useState } from "react";

export default function UploadDropzone({
  onFile,
  accept = ".pdf,.docx",
  label = "Drop a file here, or click to browse",
  sublabel = "PDF or DOCX",
  disabled = false,
  compact = false,
}) {
  const inputRef = useRef(null);
  const [isOver, setIsOver] = useState(false);

  const handleFiles = (files) => {
    if (disabled || !files || files.length === 0) return;
    onFile(files[0]);
  };

  return (
    <div
      className={`dropzone ${isOver ? "dropzone--over" : ""} ${disabled ? "dropzone--disabled" : ""} ${
        compact ? "dropzone--compact" : ""
      }`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setIsOver(true);
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <div className="dropzone__icon">↑</div>
      <div className="dropzone__label">{label}</div>
      {sublabel && <div className="dropzone__sublabel">{sublabel}</div>}
    </div>
  );
}
