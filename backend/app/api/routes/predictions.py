"""Read-only prediction and risk explanation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.datasets import require_processed_dataset
from app.repositories import prediction_repository
from app.schemas.prediction import ExplanationList, PredictionPage
from app.services import prediction_service

router = APIRouter(prefix="/api/v1/predictions", tags=["Predictions"])
learner_predictions_router = APIRouter(
    prefix="/api/v1/learners", tags=["Predictions"]
)
def _check_database():
    if prediction_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")


def _database_error(exc: Exception, detail: str):
    raise HTTPException(
        status_code=503 if str(exc) == "database_unavailable" else 500,
        detail=detail,
    ) from exc


@router.get("", response_model=PredictionPage)
def list_predictions(
    dataset_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    risk_category: str | None = Query(default=None, pattern="^(low|medium|high)$"),
    code_module: str | None = Query(default=None, min_length=1, max_length=16),
    code_presentation: str | None = Query(default=None, min_length=1, max_length=16),
    learner_id: UUID | None = None,
    _dataset: dict = Depends(require_processed_dataset),
):
    _check_database()
    try:
        return prediction_service.list_predictions(
            limit=limit,
            offset=offset,
            dataset_id=str(dataset_id),
            risk_category=risk_category,
            code_module=code_module,
            code_presentation=code_presentation,
            learner_id=str(learner_id) if learner_id else None,
        )
    except Exception as exc:
        _database_error(exc, "Unable to retrieve predictions.")


@router.get("/{prediction_id}/explanations", response_model=ExplanationList)
def get_explanations(
    prediction_id: UUID,
    dataset_id: UUID,
    _dataset: dict = Depends(require_processed_dataset),
):
    _check_database()
    try:
        prediction = prediction_repository.get_prediction(str(prediction_id), str(dataset_id))
        if prediction is None:
            raise HTTPException(status_code=404, detail="Prediction not found.")
        explanations = prediction_service.list_explanations(
            str(prediction_id), str(dataset_id)
        )
        return {"prediction_id": str(prediction_id), "data": explanations}
    except HTTPException:
        raise
    except Exception as exc:
        _database_error(exc, "Unable to retrieve risk explanations.")


@router.get("/{prediction_id}")
def get_prediction(
    prediction_id: UUID,
    dataset_id: UUID,
    _dataset: dict = Depends(require_processed_dataset),
):
    _check_database()
    try:
        prediction = prediction_service.get_prediction(str(prediction_id), str(dataset_id))
    except Exception as exc:
        _database_error(exc, "Unable to retrieve the prediction.")
    if prediction is None:
        raise HTTPException(status_code=404, detail="Prediction not found.")
    return prediction


@learner_predictions_router.get("/{learner_id}/predictions", response_model=PredictionPage)
def list_learner_predictions(
    learner_id: UUID,
    dataset_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _dataset: dict = Depends(require_processed_dataset),
):
    _check_database()
    try:
        return prediction_service.list_predictions(
            limit=limit,
            offset=offset,
            dataset_id=str(dataset_id),
            learner_id=str(learner_id),
        )
    except Exception as exc:
        _database_error(exc, "Unable to retrieve learner predictions.")
