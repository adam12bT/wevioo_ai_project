"""Database provider selection for durable worker records."""

from app.config import settings
from app.database.base import DatabaseRepository


def database_repository() -> DatabaseRepository | None:
    """Create the configured durable database repository."""

    provider = settings.database_provider
    if provider == "postgres":
        if not settings.database_url:
            if settings.database_required:
                raise RuntimeError(
                    "DATABASE_URL is required when DATABASE_PROVIDER=postgres"
                )
            return None
        from app.database.postgres import PostgresRepository

        return PostgresRepository()
    if provider == "supabase":
        from app.supabase import SupabaseRepository

        if not settings.supabase_enabled:
            if settings.database_required:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required "
                    "when DATABASE_PROVIDER=supabase"
                )
            return None
        return SupabaseRepository()
    if provider in {"none", "disabled"} and not settings.database_required:
        return None
    raise RuntimeError("DATABASE_PROVIDER must be 'postgres' or 'supabase'")


__all__ = ["DatabaseRepository", "database_repository"]
