
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_algorithm: str = "ES256"
    model_path: str = "../ml/artifacts/churn_model.joblib"

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def expected_jwt_issuer(self) -> str:
        if self.supabase_jwt_issuer.strip():
            return self.supabase_jwt_issuer.strip().rstrip("/")
        if not self.supabase_url.strip():
            return ""
        return f"{self.supabase_url.strip().rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        if not self.supabase_url.strip():
            return ""
        return f"{self.supabase_url.strip().rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
