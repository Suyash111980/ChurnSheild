"""Dataset-scoped CSV export for persisted learner records."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import require_roles
from app.api.dependencies.datasets import require_processed_dataset
from app.services.report_service import ReportTooLarge, export_learner_csv

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


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
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dataset export is unavailable.") from exc
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="churnshield-learners.csv"'},
    )
