import hashlib
from pathlib import Path
import re
import shutil
from typing import BinaryIO

from app.config import settings
from app.supabase import supabase_repository


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def prepare_storage() -> None:
    (settings.storage_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "results").mkdir(parents=True, exist_ok=True)


def safe_filename(filename: str | None, fallback: str) -> str:
    basename = Path(filename or fallback).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    return cleaned or fallback


def save_upload(job_id: str, kind: str, filename: str, stream: BinaryIO) -> Path:
    prepare_storage()
    target_dir = settings.storage_dir / "uploads" / job_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{kind}-{safe_filename(filename, kind)}"
    with target.open("wb") as destination:
        shutil.copyfileobj(stream, destination)
    return target


def validate_extension(filename: str) -> None:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type {extension!r}; expected {allowed}")


def content_digest(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def result_path(job_id: str) -> Path:
    prepare_storage()
    return settings.storage_dir / "results" / f"proposal-{job_id}.md"


def version_path(job_id: str, version: int) -> Path:
    """Return a local immutable path for one generated document version."""

    target_dir = settings.storage_dir / "results" / job_id / f"v{version}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "proposal.md"


def upload_durable(
    job_id: str,
    category: str,
    source: Path,
    content_type: str = "application/octet-stream",
) -> str | None:
    repository = supabase_repository()
    if repository is None:
        return None
    object_key = f"jobs/{job_id}/{category}/{source.name}"
    try:
        return repository.upload_file(object_key, source, content_type)
    finally:
        repository.close()


def materialize_file(
    local_path: str | None,
    object_key: str | None,
    filename: str,
) -> Path:
    if local_path and Path(local_path).is_file():
        return Path(local_path)
    if not object_key:
        raise FileNotFoundError(f"No local or durable copy is available for {filename}")
    repository = supabase_repository()
    if repository is None:
        raise RuntimeError("Supabase is required to restore the missing input file")
    try:
        content = repository.download_bytes(object_key)
    finally:
        repository.close()
    target_dir = settings.storage_dir / "restored"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_filename(filename, "document")
    target.write_bytes(content)
    return target
