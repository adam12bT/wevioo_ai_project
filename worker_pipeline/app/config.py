from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _integer(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _floating(name: str, default: float, minimum: float = 0.1) -> float:
    try:
        return max(minimum, float(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _integer_list(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    try:
        values = tuple(
            max(1, int(item.strip()))
            for item in os.environ.get(name, "").split(",")
            if item.strip()
        )
        return values or default
    except ValueError:
        return default


def _boolean(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _redis_url() -> str:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    if url.startswith("rediss://") and "ssl_cert_reqs=" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}ssl_cert_reqs=required"
    return url


@dataclass(frozen=True)
class Settings:
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    redis_url: str = _redis_url()
    queue_name: str = os.environ.get("QUEUE_NAME", "rfp-pipeline")
    job_ttl_seconds: int = _integer("JOB_TTL_SECONDS", 604800)
    result_ttl_seconds: int = _integer("RESULT_TTL_SECONDS", 604800)
    job_timeout_seconds: int = _integer("JOB_TIMEOUT_SECONDS", 7200)
    worker_max_retries: int = _integer("WORKER_MAX_RETRIES", 3)
    worker_retry_intervals_seconds: tuple[int, ...] = _integer_list(
        "WORKER_RETRY_INTERVALS_SECONDS", (10, 30, 60)
    )
    redis_event_ttl_seconds: int = _integer("REDIS_EVENT_TTL_SECONDS", 86400)
    redis_event_max_length: int = _integer("REDIS_EVENT_MAX_LENGTH", 2000)
    storage_dir: Path = Path(os.environ.get("STORAGE_DIR", "./data")).resolve()
    pipeline_base_url: str = os.environ.get(
        "PIPELINE_BASE_URL", "http://localhost:8000"
    ).rstrip("/")
    pipeline_api_key: str = os.environ.get("PIPELINE_API_KEY", "")
    pipeline_request_timeout_seconds: float = _floating(
        "PIPELINE_REQUEST_TIMEOUT_SECONDS", 120
    )
    pipeline_poll_interval_seconds: float = _floating(
        "PIPELINE_POLL_INTERVAL_SECONDS", 10
    )
    pipeline_rate_limit_backoff_seconds: float = _floating(
        "PIPELINE_RATE_LIMIT_BACKOFF_SECONDS", 30
    )
    pipeline_health_cache_seconds: float = _floating(
        "PIPELINE_HEALTH_CACHE_SECONDS", 60
    )
    pipeline_max_poll_seconds: int = _integer("PIPELINE_MAX_POLL_SECONDS", 7200)
    database_provider: str = os.environ.get(
        "DATABASE_PROVIDER", "supabase"
    ).strip().lower()
    database_url: str = os.environ.get("DATABASE_URL", "")
    database_required: bool = _boolean("DATABASE_REQUIRED", True)
    database_auto_create: bool = _boolean("DATABASE_AUTO_CREATE", True)
    supabase_url: str = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_service_role_key: str = os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY", ""
    )
    supabase_storage_bucket: str = os.environ.get(
        "SUPABASE_STORAGE_BUCKET", "rfp-files"
    )
    supabase_required: bool = _boolean("SUPABASE_REQUIRED", True)
    supabase_request_timeout_seconds: float = _floating(
        "SUPABASE_REQUEST_TIMEOUT_SECONDS", 120
    )
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")
        if item.strip()
    )

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


settings = Settings()
