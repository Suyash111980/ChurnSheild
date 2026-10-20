"""Owner-scoped dashboard data from real learner and prediction records."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.datasets import require_processed_dataset
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import get_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    dataset_id: UUID,
    dataset: dict = Depends(require_processed_dataset),
):
    try:
        summary = get_summary(str(dataset_id), dataset["owner_id"], dataset["workspace_id"])
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve dashboard data.",
        ) from exc
    if summary is None:
        raise HTTPException(status_code=404, detail="Dataset dashboard data not found.")
    return summary
