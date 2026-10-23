
from functools import lru_cache
import logging

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_supabase_client() -> Client | None:
    """Create a server-side Supabase client when credentials are configured."""
    missing_settings = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SECRET_KEY", settings.supabase_secret_key),
        )
        if not value.strip()
    ]
    if missing_settings:
        logger.error(
            "Supabase client is unavailable; missing backend settings: %s",
            ", ".join(missing_settings),
        )
        return None

    try:
        return create_client(
            settings.supabase_url,
            settings.supabase_secret_key,
        )
    except Exception as exc:
        # Keep non-database endpoints available when configuration is invalid.
        # Callers report a generic service-unavailable response when needed.
        logger.error("Supabase client initialization failed (exception_type=%s)", type(exc).__name__)
        return None


supabase = get_supabase_client()
