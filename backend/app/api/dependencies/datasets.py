"""Authorization boundary for service-role queries scoped to owned datasets."""

import logging
import re
from uuid import UUID

from fastapi import Depends, HTTPException

from app.api.dependencies.auth import require_roles
from app.repositories import dataset_repository

logger = logging.getLogger(__name__)


def _safe_provider_code(exc: Exception) -> str:
    """Return only a bounded provider error code, never raw database text."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", code):
        return code
    return "unavailable"


def require_admin_workspace(
    user: dict = Depends(require_roles("admin", "master_admin")),
) -> dict:
    """Resolve the sole workspace from the authenticated Admin identity."""
    if dataset_repository.supabase is None:
        logger.error("Admin workspace verification unavailable: Supabase client is not initialized")
        raise HTTPException(status_code=503, detail="Workspace service is not configured.")
    try:
        workspace = dataset_repository.get_workspace_for_admin(user["id"])
    except Exception as exc:
        logger.error(
            "Admin workspace lookup failed (exception_type=%s provider_code=%s)",
            type(exc).__name__,
            _safe_provider_code(exc),
        )
        raise HTTPException(status_code=503, detail="Workspace access could not be verified.") from exc
    if not workspace or workspace.get("status") != "active":
        logger.warning("Authenticated Admin has no active workspace")
        raise HTTPException(status_code=403, detail="An active Admin workspace is required.")
    return {**user, "workspace_id": workspace["id"]}


def require_owned_dataset(
    dataset_id: UUID,
    user: dict = Depends(require_admin_workspace),
) -> dict:
    """Resolve ownership from the trusted dataset table, never the request body."""
    if dataset_repository.supabase is None:
        logger.error("Dataset ownership verification unavailable: Supabase client is not initialized")
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        dataset = dataset_repository.get_owned_dataset(
            str(dataset_id), user["id"], user["workspace_id"]
        )
    except Exception as exc:
        logger.error(
            "Dataset ownership lookup failed (exception_type=%s provider_code=%s)",
            type(exc).__name__,
            _safe_provider_code(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="Dataset ownership could not be verified.",
        ) from exc
    if dataset is None:
        # A single not-found response avoids revealing another user's dataset IDs.
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


def require_processed_dataset(
    dataset: dict = Depends(require_owned_dataset),
) -> dict:
    """Prevent partial rows from a failed or still-running import being served."""
    if dataset.get("status") != "processed":
        raise HTTPException(
            status_code=409,
            detail="Dataset processing has not completed.",
        )
    return dataset


def resolve_processed_dataset_scope(dataset_id: str, user: dict) -> list[dict]:
    """Resolve one owned processed dataset or all processed datasets in a workspace."""
    if dataset_id == "all":
        try:
            datasets = dataset_repository.list_all_owned_datasets(
                owner_id=user["id"], workspace_id=user["workspace_id"]
            )
        except Exception as exc:
            logger.error("Workspace dataset scope lookup failed (exception_type=%s)", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Workspace datasets could not be verified.") from exc
        return [row for row in datasets if row.get("status") == "processed"]

    try:
        normalized_id = str(UUID(dataset_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid dataset id.") from exc
    if dataset_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        dataset = dataset_repository.get_owned_dataset(
            normalized_id, user["id"], user["workspace_id"]
        )
    except Exception as exc:
        logger.error("Dataset scope lookup failed (exception_type=%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Dataset access could not be verified.") from exc
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if dataset.get("status") != "processed":
        raise HTTPException(status_code=409, detail="Dataset processing has not completed.")
    return [dataset]
