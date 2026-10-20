"""Master Admin-only review of requested Admin accounts."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies.auth import require_roles
from app.integrations.supabase_client import supabase

router = APIRouter(prefix="/api/v1/admin", tags=["Master Admin"])


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]


def _service():
    if supabase is None:
        raise HTTPException(status_code=503, detail="User profile service is not configured.")
    return supabase


@router.get("/pending-users")
def list_pending_users(_master: dict = Depends(require_roles("master_admin"))):
    try:
        client = _service()
        pending = (client.table("profiles").select("id, role, requested_role, approval_status, created_at")
                   .eq("requested_role", "admin").eq("approval_status", "pending")
                   .order("created_at").execute()).data or []
        all_profiles = (client.table("profiles").select("id, role, requested_role, approval_status, created_at")
                        .order("created_at", desc=True).execute()).data or []
        master_id = _master.get("id")
        accounts = [row for row in all_profiles if row.get("requested_role") == "admin" or
                    (row.get("role") == "admin" and row.get("id") != master_id)]
        workspaces = (client.table("workspaces").select("id, admin_user_id, status, created_at").execute()).data or []
        datasets = client.table("dataset_uploads").select("id, workspace_id, status").execute().data or []
        dataset_summary: dict[str, dict] = {}
        for row in datasets:
            workspace_id = row.get("workspace_id")
            if workspace_id is None:
                continue
            summary = dataset_summary.setdefault(workspace_id, {"dataset_count": 0, "processing_status_counts": {}})
            summary["dataset_count"] += 1
            state = str(row.get("status") or "unknown")
            summary["processing_status_counts"][state] = summary["processing_status_counts"].get(state, 0) + 1
        workspace_by_admin = {row["admin_user_id"]: row for row in workspaces}
        for account in accounts:
            workspace = workspace_by_admin.get(account["id"])
            account["workspace"] = ({**workspace, **dataset_summary.get(workspace["id"], {"dataset_count": 0, "processing_status_counts": {}})} if workspace else None)
        return {"data": pending, "accounts": accounts}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Admin requests are temporarily unavailable.") from exc


@router.patch("/users/{user_id}/approval")
def review_admin_request(
    user_id: UUID,
    decision: ReviewDecision,
    _master: dict = Depends(require_roles("master_admin")),
):
    try:
        result = _service().rpc("master_review_admin_request", {
            "target_user_id": str(user_id), "decision": decision.decision
        }).execute()
    except Exception as exc:
        # Keep provider/database errors distinct from denied user authorization.
        raise HTTPException(status_code=503, detail="Admin request review is temporarily unavailable.") from exc
    rows = result.data
    if isinstance(rows, list):
        rows = rows[0] if rows else None
    if not isinstance(rows, dict):
        raise HTTPException(status_code=503, detail="Admin request review returned an invalid response.")
    return {"data": rows}
