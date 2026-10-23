"""Dataset-scoped CSV export for persisted learner records."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import require_roles
from app.api.dependencies.datasets import require_processed_dataset
from app.services.report_service import (
    ReportTooLarge,
    ReportUnavailable,
    export_learner_csv,
    export_recommendations_csv,
    export_risk_analysis_csv,
)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def _csv_response(csv_data: str, filename: str):
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/learners.csv")
def export_learners(
    dataset_id: UUID,
    _user: dict = Depends(require_roles("admin")),
    _dataset: dict = Depends(require_processed_dataset),
):
    try:
        csv_data, _count = export_learner_csv(str(dataset_id))
    except ReportTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ReportUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dataset export is unavailable.") from exc
    return _csv_response(csv_data, "churnshield-learners.csv")


@router.get("/risk-analysis.csv")
def export_risk_analysis(
    dataset_id: UUID,
    _user: dict = Depends(require_roles("admin")),
    _dataset: dict = Depends(require_processed_dataset),
):
    try:
        csv_data, _count = export_risk_analysis_csv(str(dataset_id))
    except ReportTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ReportUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Risk analysis export is unavailable.") from exc
    return _csv_response(csv_data, "churnshield-risk-analysis.csv")


@router.get("/recommendations.csv")
def export_recommendations(
    dataset_id: UUID,
    _user: dict = Depends(require_roles("admin")),
    _dataset: dict = Depends(require_processed_dataset),
):
    try:
        csv_data, _count = export_recommendations_csv(str(dataset_id))
    except ReportTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ReportUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Recommendation export is unavailable.") from exc
    return _csv_response(csv_data, "churnshield-recommendations.csv")
