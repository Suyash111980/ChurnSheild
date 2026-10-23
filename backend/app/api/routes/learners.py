
from typing import Literal
from uuid import UUID
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.datasets import (
    require_admin_workspace,
    require_processed_dataset,
    resolve_processed_dataset_scope,
)
from app.repositories import learner_repository
from app.schemas.learner import LearnerPage, LearnerProfile
from app.services import learner_service

router = APIRouter(prefix="/api/v1/learners", tags=["Learners"])


@router.get("")
def get_learners(
    dataset_id: UUID | None = Query(default=None),
    scope: Literal["all"] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    id_student: str | None = Query(default=None, min_length=1, max_length=64),
    code_module: str | None = Query(default=None, min_length=1, max_length=16),
    code_presentation: str | None = Query(default=None, min_length=1, max_length=16),
    risk_category: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    q: str | None = Query(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9 _-]+$"),
    sort: str | None = Query(default=None, pattern="^(id_student|code_module|code_presentation|highest_education|region|latest_risk_probability|latest_risk_category)$"),
    direction: str = Query(default="asc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_admin_workspace),
) -> LearnerPage:
    if learner_repository.supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Database service is not configured.",
        )

    if (scope == "all") == (dataset_id is not None):
        raise HTTPException(status_code=422, detail="Provide either a dataset_id or scope=all.")
    if scope == "all":
        datasets = resolve_processed_dataset_scope("all", user)
        dataset_ids = [row["id"] for row in datasets]
        selected_dataset_id = None
    else:
        selected_dataset_id = str(dataset_id)
        datasets = resolve_processed_dataset_scope(selected_dataset_id, user)
        dataset_ids = None

    if q and not re.fullmatch(r"[A-Za-z0-9 _-]{1,64}", q):
        raise HTTPException(status_code=422, detail="Search contains unsupported characters.")
    try:
        return learner_service.list_learners(
            limit=limit,
            offset=offset,
            dataset_id=selected_dataset_id,
            dataset_ids=dataset_ids,
            id_student=id_student,
            code_module=code_module,
            code_presentation=code_presentation,
            risk_category=risk_category,
            search=q,
            sort=sort,
            direction=direction,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve learners from the database.",
        ) from exc


@router.get("/{learner_id}", response_model=LearnerProfile)
def get_learner_profile(
    learner_id: UUID,
    dataset_id: UUID,
    _dataset: dict = Depends(require_processed_dataset),
) -> LearnerProfile:
    if learner_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        profile = learner_service.get_learner_profile(str(learner_id), str(dataset_id))
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve the learner profile.",
        ) from exc
    if profile is None:
        raise HTTPException(status_code=404, detail="Learner record not found.")
    return profile
