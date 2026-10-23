"""Owner-scoped dashboard data from real learner and prediction records."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.datasets import require_admin_workspace
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import get_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    dataset_id: UUID | None = Query(default=None),
    scope: Literal["all"] | None = Query(default=None),
    user: dict = Depends(require_admin_workspace),
):
    if (scope == "all") == (dataset_id is not None):
        raise HTTPException(status_code=422, detail="Provide either a dataset_id or scope=all.")
    requested_scope = "all" if scope == "all" else str(dataset_id)
    try:
        summary = get_summary(requested_scope, user["id"], user["workspace_id"])
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve dashboard data.",
        ) from exc
    if summary is None:
        raise HTTPException(status_code=404, detail="Dataset dashboard data not found.")
    return summary
