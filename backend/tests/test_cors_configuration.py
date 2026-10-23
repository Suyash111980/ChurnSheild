from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, settings
from app.main import app


def test_default_cors_allowlist_covers_both_vite_local_ports(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    configured = Settings(_env_file=None)

    assert configured.cors_origin_list == [
        "http://localhost:5173",
        "http://localhost:5174",
    ]
    assert "*" not in configured.cors_origin_list


def test_app_cors_middleware_uses_explicit_origins_and_auth_headers():
    middleware = next(layer for layer in app.user_middleware if layer.cls is CORSMiddleware)
    options = middleware.kwargs

    assert options["allow_origins"] == settings.cors_origin_list
    assert "*" not in options["allow_origins"]
    assert options["allow_credentials"] is True
    assert {"GET", "POST", "OPTIONS"}.issubset(set(options["allow_methods"]))
    assert {"Authorization", "Content-Type"}.issubset(set(options["allow_headers"]))
