from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AdminRequestStatus = Literal["pending", "approved", "rejected"]
AdminRequestAction = Literal["submitted", "approved", "rejected"]


class AdminRequestRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    display_name: str = "Unknown user"
    email: str | None = None
    status: AdminRequestStatus
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer_name: str | None = None
    reviewer_email: str | None = None
    rejection_reason: str | None = None


class AdminRequestActivity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: AdminRequestAction
    target_display_name: str = "Unknown user"
    target_email: str | None = None
    actor_display_name: str | None = None
    actor_email: str | None = None
    rejection_reason: str | None = None
    created_at: datetime


class AdminRequestCounts(BaseModel):
    pending: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)


class AdminRequestPage(BaseModel):
    data: list[AdminRequestRecord]
    counts: AdminRequestCounts
    count: int = Field(ge=0)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool
    activity: list[AdminRequestActivity]


class AdminAssignedWorkspace(BaseModel):
    workspace_name: str | None = None
    workspace_id: str
    assigned_at: datetime | None = None


class AdminUploadedDataset(BaseModel):
    filename: str
    uploaded_at: datetime | None = None
    row_count: int | None = Field(default=None, ge=0)


class AdminRequestDetails(BaseModel):
    workspaces: list[AdminAssignedWorkspace]
    datasets: list[AdminUploadedDataset]


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    rejection_reason: str | None = Field(default=None, max_length=1000)


class AdminRequestReviewResult(BaseModel):
    id: str
    role: str
    approval_status: Literal["approved", "denied"]
    reviewed_at: datetime
    reviewed_by: str
    workspace_id: str | None = None
