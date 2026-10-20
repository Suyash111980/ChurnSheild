"""Paginated early-warning data using persisted latest predictions only."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from uuid import UUID

from app.api.dependencies.datasets import require_processed_dataset
from app.repositories import learner_repository
from app.schemas.recommendation import EarlyWarningPage
from app.services.learner_service import get_early_warning_page

router = APIRouter(prefix="/api/v1/early-warning", tags=["Early Warning"])


@router.get("", response_model=EarlyWarningPage)
def early_warning(
    dataset_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    risk_category: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    code_module: str | None = Query(default=None, min_length=1, max_length=16),
    code_presentation: str | None = Query(default=None, min_length=1, max_length=16),
    _dataset: dict = Depends(require_processed_dataset),
):
    if learner_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        return get_early_warning_page(
            dataset_id=str(dataset_id),
            limit=limit,
            offset=offset,
            risk_category=risk_category,
            code_module=code_module,
            code_presentation=code_presentation,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve early-warning data.",
        ) from exc
