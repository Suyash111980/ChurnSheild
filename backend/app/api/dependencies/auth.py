
import logging
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import (
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWKSetError,
    PyJWTError,
)

from app.core.config import settings
from app.integrations.supabase_client import supabase

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)
SUPPORTED_JWKS_ALGORITHMS = {"ES256", "RS256"}
DATABASE_TO_APP_ROLE = {
    "admin": "admin",
}


def _http_error(
    code: int,
    detail: str,
    *,
    bearer: bool = False,
) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if bearer else None
    return HTTPException(
        status_code=code,
        detail=detail,
        headers=headers,
    )


@lru_cache(maxsize=1)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True, timeout=5)


def _get_authenticated_profile(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict[str, Any]:
    """Verify the Supabase token and load trusted profile approval and role."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        )

    issuer = settings.expected_jwt_issuer
    jwks_url = settings.supabase_jwks_url
    algorithm = settings.supabase_jwt_algorithm.strip().upper()

    if not issuer or not jwks_url:
        logger.error("Authentication configuration is incomplete.")
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication service is not configured.",
        )

    if algorithm not in SUPPORTED_JWKS_ALGORITHMS:
        logger.error("Unsupported JWT signing algorithm configured.")
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication signing configuration is unsupported.",
        )

    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        ) from exc

    if header.get("alg") != algorithm or not header.get("kid"):
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        )

    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(
            token
        )
    except (PyJWKClientConnectionError, PyJWKSetError) as exc:
        logger.warning(
            "Supabase JWKS lookup failed; exception_type=%s",
            type(exc).__name__,
        )
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication provider is temporarily unavailable.",
        ) from exc
    except PyJWKClientError as exc:
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        ) from exc

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except PyJWTError as exc:
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        ) from exc

    subject = claims.get("sub")

    if claims.get("role") != "authenticated" or not isinstance(
        subject, str
    ):
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        )

    try:
        subject = str(UUID(subject))
    except ValueError as exc:
        raise _http_error(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing authentication token.",
            bearer=True,
        ) from exc

    if supabase is None:
        logger.error("Supabase profile client is not initialized.")
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "User profile service is not configured.",
        )

    try:
        response = (
            supabase.table("profiles")
            .select("id, role, approval_status")
            .eq("id", subject)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        # Log only the exception type and a sanitized error code.
        # Never log tokens, request headers, or the full error message.
        raw_code = getattr(exc, "code", None)

        if (
            isinstance(raw_code, int)
            and not isinstance(raw_code, bool)
            and 100 <= raw_code <= 599
        ):
            safe_code = str(raw_code)
        elif (
            isinstance(raw_code, str)
            and raw_code.replace("_", "").isalnum()
        ):
            safe_code = raw_code
        else:
            safe_code = "unavailable"

        logger.error(
            "Profile lookup failed; exception_type=%s; error_code=%s",
            type(exc).__name__,
            safe_code,
        )

        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "User profile service is temporarily unavailable.",
        ) from exc

    rows = response.data or []
    profile = rows[0] if rows else None

    if not isinstance(profile, dict) or str(profile.get("id")) != subject:
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "A valid ChurnShield profile is required.",
        )

    database_role = profile.get("role")

    if not isinstance(database_role, str):
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "The ChurnShield profile has no recognized role.",
        )

    app_role = DATABASE_TO_APP_ROLE.get(database_role)
    approval_status = profile.get("approval_status")
    master_admin_id = settings.master_admin_user_id.strip().lower()

    if (
        master_admin_id
        and subject.lower() == master_admin_id
        and database_role == "admin"
        and approval_status == "approved"
    ):
        app_role = "master_admin"

    # Pending and denied users may read their own approval state.
    if app_role is None and approval_status == "approved":
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "The ChurnShield profile has no recognized role.",
        )

    return {
        "id": subject,
        "database_role": database_role,
        "app_role": app_role,
        "approval_status": approval_status,
    }


def get_authenticated_profile(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> dict[str, Any]:
    """Authenticate a user and expose their trusted approval state."""
    return _get_authenticated_profile(credentials)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> dict[str, Any]:
    """Require an approved profile before protected application access."""
    profile = _get_authenticated_profile(credentials)
    approval_status = profile["approval_status"]

    if approval_status == "pending":
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "Your account is awaiting administrator approval.",
        )

    if approval_status == "denied":
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "An administrator denied access to this account.",
        )

    if approval_status != "approved":
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "Your account requires administrator review before access.",
        )

    if profile["app_role"] is None:
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "The ChurnShield profile has no recognized role.",
        )

    return profile


def require_roles(*allowed_roles: str):
    """Build a dependency that permits only the named ChurnShield roles."""
    allowed = frozenset(allowed_roles)
    recognized_roles = {"admin", "master_admin"}

    if not allowed or not allowed.issubset(recognized_roles):
        raise ValueError(
            "At least one recognized ChurnShield role is required."
        )

    def check_role(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if current_user["app_role"] not in allowed:
            raise _http_error(
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to access this resource.",
            )

        return current_user

    return check_role
