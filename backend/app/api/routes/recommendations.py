"""Recommendation listing and authorized status updates."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.auth import require_roles
from app.api.dependencies.datasets import require_processed_dataset
from app.repositories import recommendation_repository
from app.schemas.recommendation import RecommendationPage, RecommendationStatusUpdate
from app.services import recommendation_service

router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])


@router.get("", response_model=RecommendationPage)
def list_recommendations(
    dataset_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    learner_id: UUID | None = None,
    prediction_id: UUID | None = None,
    recommendation_status: str | None = Query(
        default=None, alias="status", pattern="^(pending|in_progress|completed|dismissed)$"
    ),
    risk_level: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    _dataset: dict = Depends(require_processed_dataset),
):
    if recommendation_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        return recommendation_service.list_recommendations(
            limit=limit,
            offset=offset,
            dataset_id=str(dataset_id),
            learner_id=str(learner_id) if learner_id else None,
            prediction_id=str(prediction_id) if prediction_id else None,
            recommendation_status=recommendation_status,
            risk_level=risk_level,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve recommendations.",
        ) from exc


@router.patch("/{recommendation_id}")
def update_recommendation(
    recommendation_id: UUID,
    dataset_id: UUID,
    update: RecommendationStatusUpdate,
    current_user: dict = Depends(require_roles("admin")),
    _dataset: dict = Depends(require_processed_dataset),
):
    if recommendation_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    try:
        result = recommendation_service.update_status(
            str(recommendation_id), str(dataset_id), update.status
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That recommendation status transition is not allowed.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to update the recommendation.",
        ) from exc

    if result is None:
        # A missing record and a concurrent status change are distinguished by
        # one bounded existence read only when the conditional update lost a race.
        try:
            exists = recommendation_repository.get_recommendation(
                str(recommendation_id), str(dataset_id)
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Recommendation service unavailable.") from exc
        if exists is None:
            raise HTTPException(status_code=404, detail="Recommendation not found.")
        raise HTTPException(status_code=409, detail="Recommendation status changed; refresh and retry.")
    return {"data": result}
