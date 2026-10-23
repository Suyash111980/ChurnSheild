"""Dataset-scoped course insight endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.datasets import require_admin_workspace
from app.repositories import learner_repository
from app.schemas.dashboard import CourseInsights
from app.services.dashboard_service import get_course_insights

router = APIRouter(prefix="/api/v1/courses", tags=["Course Insights"])


@router.get("/insights", response_model=CourseInsights)
def course_insights(
    dataset_id: UUID | None = Query(default=None),
    scope: Literal["all"] | None = Query(default=None),
    user: dict = Depends(require_admin_workspace),
):
    if learner_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")
    if (scope == "all") == (dataset_id is not None):
        raise HTTPException(status_code=422, detail="Provide either a dataset_id or scope=all.")
    requested_scope = "all" if scope == "all" else str(dataset_id)
    try:
        result = get_course_insights(
            requested_scope, user["id"], user["workspace_id"]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503 if str(exc) == "database_unavailable" else 500,
            detail="Unable to retrieve course insights.",
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return result
