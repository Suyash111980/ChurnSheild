
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.datasets import require_processed_dataset
from app.repositories import learner_repository
from app.schemas.learner import LearnerPage, LearnerProfile
from app.services import learner_service

router = APIRouter(prefix="/api/v1/learners", tags=["Learners"])


@router.get("")
def get_learners(
    dataset_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    id_student: str | None = Query(default=None, min_length=1, max_length=64),
    code_module: str | None = Query(default=None, min_length=1, max_length=16),
    code_presentation: str | None = Query(default=None, min_length=1, max_length=16),
    risk_category: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    _dataset: dict = Depends(require_processed_dataset),
) -> LearnerPage:
    if learner_repository.supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Database service is not configured.",
        )

    try:
        return learner_service.list_learners(
            limit=limit,
            offset=offset,
            dataset_id=str(dataset_id),
            id_student=id_student,
            code_module=code_module,
            code_presentation=code_presentation,
            risk_category=risk_category,
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
