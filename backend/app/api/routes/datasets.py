"""Owner-scoped dataset preview, upload, processing, list, detail, and retry APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.api.dependencies.datasets import require_admin_workspace
from app.repositories import dataset_repository
from app.schemas.dataset import DatasetPage, DatasetPreview, DatasetRecord
from app.services import dataset_service
from app.utils.dataset_parser import MAX_UPLOAD_BYTES, DatasetUploadError

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])


async def _upload_bytes(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    return content


def _ensure_database():
    if dataset_repository.supabase is None:
        raise HTTPException(status_code=503, detail="Database service is not configured.")


def _database_error(exc: Exception, message: str):
    raise HTTPException(
        status_code=503 if str(exc) == "database_unavailable" else 500,
        detail=message,
    ) from exc


@router.post("/preview", response_model=DatasetPreview)
async def preview_dataset(
    file: UploadFile = File(...),
    _user: dict = Depends(require_admin_workspace),
):
    content = await _upload_bytes(file)
    try:
        return dataset_service.preview_upload(file.filename or "dataset.csv", content)
    except DatasetUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/upload", status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str = Form(default=""),
    user: dict = Depends(require_admin_workspace),
):
    _ensure_database()
    content = await _upload_bytes(file)
    try:
        return dataset_service.upload_dataset(
            owner_id=user["id"],
            workspace_id=user["workspace_id"],
            filename=file.filename or "dataset.csv",
            dataset_name=dataset_name,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Dataset cannot be retried in its current state.") from exc
    except Exception as exc:
        _database_error(exc, "Dataset upload could not be processed.")


@router.get("", response_model=DatasetPage)
def list_datasets(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_admin_workspace),
):
    _ensure_database()
    try:
        return dataset_service.list_owned_datasets(
            owner_id=user["id"], workspace_id=user["workspace_id"], limit=limit, offset=offset
        )
    except Exception as exc:
        _database_error(exc, "Unable to retrieve datasets.")


@router.get("/{dataset_id}", response_model=DatasetRecord)
def get_dataset(
    dataset_id: UUID,
    user: dict = Depends(require_admin_workspace),
):
    _ensure_database()
    try:
        record = dataset_service.get_owned_dataset(str(dataset_id), user["id"], user["workspace_id"])
    except Exception as exc:
        _database_error(exc, "Unable to retrieve the dataset.")
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return record


@router.post("/{dataset_id}/retry", status_code=202)
async def retry_dataset(
    dataset_id: UUID,
    file: UploadFile = File(...),
    user: dict = Depends(require_admin_workspace),
):
    _ensure_database()
    content = await _upload_bytes(file)
    try:
        result = dataset_service.upload_dataset(
            owner_id=user["id"],
            workspace_id=user["workspace_id"],
            filename=file.filename or "dataset.csv",
            dataset_name="",
            content=content,
            dataset_id=str(dataset_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Only failed datasets can be retried.") from exc
    except Exception as exc:
        _database_error(exc, "Dataset retry could not be processed.")
    if result["data"] is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return result


@router.post("/{dataset_id}/reprocess", status_code=202)
async def reprocess_dataset(
    dataset_id: UUID,
    file: UploadFile = File(...),
    user: dict = Depends(require_admin_workspace),
):
    """Reprocess an owned dataset using its stable dataset and learner IDs."""
    _ensure_database()
    content = await _upload_bytes(file)
    try:
        result = dataset_service.upload_dataset(
            owner_id=user["id"],
            workspace_id=user["workspace_id"],
            filename=file.filename or "dataset.csv",
            dataset_name="",
            content=content,
            dataset_id=str(dataset_id),
            allow_reprocess=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Dataset cannot be reprocessed in its current state.") from exc
    except Exception as exc:
        _database_error(exc, "Dataset reprocessing could not be completed.")
    if result["data"] is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return result
