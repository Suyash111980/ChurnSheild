from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator

from app.api.dependencies.auth import require_roles
from app.integrations.supabase_client import supabase

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

APP_TO_DATABASE_ROLE = {
    "admin": "admin",
    "retention_manager": "educator",
    "data_analyst": "analyst",
}


class ApprovalUpdate(BaseModel):
    approval_status: Literal["approved", "denied"]
    role: Literal["admin", "retention_manager", "data_analyst"] | None = None

    @model_validator(mode="after")
    def require_role_for_approval(self):
        if self.approval_status == "approved" and self.role is None:
            raise ValueError("A role is required when approving an account.")
        if self.approval_status == "denied" and self.role is not None:
            raise ValueError("A role cannot be assigned to a denied account.")
        return self


@router.get("/pending-users")
def list_pending_users(
    _admin: dict = Depends(require_roles("admin")),
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User profile service is not configured.",
        )

    try:
        response = (
            supabase.table("profiles")
            .select("id, role, approval_status, created_at")
            .eq("approval_status", "pending")
            .order("created_at")
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User profile service is temporarily unavailable.",
        ) from exc

    return {"data": response.data or []}


@router.patch("/users/{user_id}/approval")
def update_user_approval(
    user_id: UUID,
    decision: ApprovalUpdate,
    _admin: dict = Depends(require_roles("admin")),
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User profile service is not configured.",
        )

    updates = {"approval_status": decision.approval_status}
    if decision.approval_status == "approved":
        updates["role"] = APP_TO_DATABASE_ROLE[decision.role]

    try:
        response = (
            supabase.table("profiles")
            .update(updates)
            .eq("id", str(user_id))
            .eq("approval_status", "pending")
            .select("id, role, approval_status")
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User profile service is temporarily unavailable.",
        ) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending account was found for that user.",
        )
    return {"data": rows[0]}
