"""
Environment configuration for the extraction service.

All values are overridable via environment variables (or a `.env` file, see
`.env.example`). Nothing here is a secret except `ANYTHINGLLM_API_KEY`.
"""
from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Upload limits -----------------------------------------------------
    max_file_size_mb: int = 50
    allowed_extensions: tuple[str, ...] = (".pdf", ".docx")

    # --- OCR -----------------------------------------------------------------
    # Tesseract syntax for bilingual documents. Both language packs must be installed.
    ocr_language: str = "eng+fra"
    ocr_engine: str = "tesseract"  # "tesseract" | "surya"
    # A PDF page is only sent to OCR if its native extracted text has fewer
    # than this many characters. Prevents wasting time OCR-ing pages that
    # already have perfectly good native text.
    min_native_text_chars: int = 20
    ocr_dpi: int = 300

    # --- Table extraction ------------------------------------------------
    table_extraction_engine: str = "pdfplumber"  # "pdfplumber" | "camelot"
    scanned_table_extraction_enabled: bool = True

    # --- AnythingLLM integration ------------------------------------------
    anythingllm_url: str = "https://adambouacida7-ai-cv.hf.space"
    anythingllm_api_key: str = ""
    anythingllm_timeout_seconds: float = 60.0
    anythingllm_max_retries: int = 3
    anythingllm_retry_backoff_seconds: float = 0.5
    anythingllm_rollback_on_failure: bool = True

    # --- Misc ------------------------------------------------------------
    request_timeout_seconds: float = 120.0
    temp_dir: str = os.path.join(tempfile.gettempdir(), "anythingllm-extractor")
    log_level: str = "INFO"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def ensure_temp_dir(self) -> Path:
        configured = self.temp_dir.strip() if self.temp_dir else ""
        path = Path(configured or os.path.join(tempfile.gettempdir(), "anythingllm-extractor"))
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Use `get_settings.cache_clear()` in tests
    if you need to reload environment variables."""
    return Settings()
