
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase_client() -> Client | None:
    """Create a server-side Supabase client when credentials are configured."""
    if not settings.supabase_url or not settings.supabase_secret_key:
        return None

    try:
        return create_client(
            settings.supabase_url,
            settings.supabase_secret_key,
        )
    except Exception:
        # Keep non-database endpoints available when configuration is invalid.
        # Callers report a generic service-unavailable response when needed.
        return None


supabase = get_supabase_client()
