
from functools import lru_cache
import logging

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_supabase_client() -> Client | None:
    """Create a server-side Supabase client when credentials are configured."""
    if not settings.supabase_url or not settings.supabase_secret_key:
        logger.error("Supabase client is unavailable: required server configuration is missing")
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
