"""Dataset upload and owner-scoped response contracts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    owner_id: str
    dataset_name: str
    filename: str
    status: Literal["uploaded", "validated", "processing", "processed", "failed"]
    uploaded_at: str | None = None
    updated_at: str | None = None
    row_count: int | None = None
    file_size_bytes: int | None = None
    descriptive_compatible: bool = False
    prediction_compatible: bool = False
    processing_progress: int = 0
    processed_at: str | None = None
    error_summary: str | None = None
    validation_results: dict[str, Any] = Field(default_factory=dict)


class DatasetPage(BaseModel):
    data: list[DatasetRecord]
    limit: int
    offset: int
    count: int
    total: int
    has_more: bool


class DatasetPreview(BaseModel):
    filename: str
    file_size_bytes: int
    row_count: int
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    validation: dict[str, Any]
