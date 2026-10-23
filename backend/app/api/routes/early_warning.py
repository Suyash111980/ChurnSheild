"""Paginated early-warning data using persisted latest predictions only."""

from typing import Literal
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from uuid import UUID

from app.api.dependencies.datasets import require_admin_workspace, resolve_processed_dataset_scope
from app.repositories import learner_repository
from app.schemas.recommendation import EarlyWarningPage
from app.services.learner_service import get_early_warning_page

router = APIRouter(prefix="/api/v1/early-warning", tags=["Early Warning"])


@router.get("", response_model=EarlyWarningPage)
def early_warning(
    dataset_id: UUID | None = Query(default=None),
    scope: Literal["all"] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    risk_category: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    code_module: str | None = Query(default=None, min_length=1, max_length=16),
    code_presentation: str | None = Query(default=None, min_length=1, max_length=16),
    q: str | None = Query(default=None, min_length=1, max_length=64),
    user: dict = Depends(require_admin_workspace),
):
    if learner_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        if (scope == "all") == (dataset_id is not None):
            raise HTTPException(status_code=422, detail="Provide either a dataset_id or scope=all.")
        if q and not re.fullmatch(r"[A-Za-z0-9 _-]{1,64}", q):
            raise HTTPException(status_code=422, detail="Search contains unsupported characters.")
        if scope == "all":
            datasets = resolve_processed_dataset_scope("all", user)
            dataset_ids = [row["id"] for row in datasets]
            selected_dataset_id = None
        else:
            selected_dataset_id = str(dataset_id)
            datasets = resolve_processed_dataset_scope(selected_dataset_id, user)
            dataset_ids = None
        return get_early_warning_page(
            dataset_id=selected_dataset_id,
            dataset_ids=dataset_ids,
            limit=limit,
            offset=offset,
            risk_category=risk_category,
            code_module=code_module,
            code_presentation=code_presentation,
            search=q,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve early-warning data.",
        ) from exc
