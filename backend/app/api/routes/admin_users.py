"""Master Admin-only review of requested Admin accounts."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from app.api.dependencies.auth import require_roles
from app.integrations.supabase_client import supabase
from app.schemas.admin_request import (
    AdminRequestDetails,
    AdminRequestPage,
    AdminRequestReviewResult,
    ReviewDecision,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Master Admin"])


def _service():
    if supabase is None:
        raise HTTPException(status_code=503, detail="User profile service is not configured.")
    return supabase


@router.get("/requests", response_model=AdminRequestPage)
def list_admin_requests(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
    search: str | None = Query(default=None, max_length=120),
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = Query(default="newest", pattern="^(newest|oldest|reviewed)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _master: dict = Depends(require_roles("master_admin")),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="The request date range is invalid.")
    try:
        response = _service().rpc("master_list_admin_requests", {
            "status_filter": status,
            "search_query": search,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "sort_by": sort,
            "page_limit": limit,
            "page_offset": offset,
        }).execute()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Admin requests are temporarily unavailable.") from exc
    payload = getattr(response, "data", None)
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="Admin request listing returned an invalid response.")
    try:
        return AdminRequestPage.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=503, detail="Admin request listing returned an invalid response.") from exc


@router.get("/requests/{user_id}/details", response_model=AdminRequestDetails)
def get_admin_request_details(
    user_id: UUID,
    _master: dict = Depends(require_roles("master_admin")),
):
    """Return only workspace assignments and datasets owned by this admin request."""
    client = _service()
    try:
        target = (
            client.table("profiles")
            .select("id")
            .eq("id", str(user_id))
            .eq("requested_role", "admin")
            .limit(1)
            .execute()
        ).data or []
        if not target:
            raise HTTPException(status_code=404, detail="The Admin request was not found.")

        workspace_rows = (
            client.table("workspaces")
            .select("id, created_at")
            .eq("admin_user_id", str(user_id))
            .order("created_at", desc=True)
            .execute()
        ).data or []
        dataset_rows = (
            client.table("dataset_uploads")
            .select("filename, uploaded_at, row_count")
            .eq("owner_id", str(user_id))
            .order("uploaded_at", desc=True)
            .execute()
        ).data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Admin request details are temporarily unavailable.") from exc

    return AdminRequestDetails(
        workspaces=[
            {
                # The current workspaces schema has no name column.
                "workspace_name": None,
                "workspace_id": str(row["id"]),
                "assigned_at": row.get("created_at"),
            }
            for row in workspace_rows
            if row.get("id")
        ],
        datasets=[
            {
                "filename": row["filename"],
                "uploaded_at": row.get("uploaded_at"),
                "row_count": row.get("row_count"),
            }
            for row in dataset_rows
            if isinstance(row.get("filename"), str) and row["filename"].strip()
        ],
    )


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
            "target_user_id": str(user_id),
            "decision": decision.decision,
            "reviewer_user_id": str(_master["id"]),
            "review_reason": decision.rejection_reason,
        }).execute()
    except Exception as exc:
        # Map only the database's fixed domain error identifiers; never expose
        # provider messages or SQL details to the caller.
        domain_error = getattr(exc, "message", None)
        if domain_error == "request_already_reviewed":
            raise HTTPException(status_code=409, detail="This request has already been reviewed. Refresh the list.") from exc
        if domain_error == "admin_request_not_found":
            raise HTTPException(status_code=404, detail="The Admin request was not found.") from exc
        if domain_error == "reviewer_not_approved_admin":
            raise HTTPException(status_code=403, detail="The reviewing account is no longer authorized.") from exc
        raise HTTPException(status_code=503, detail="Admin request review is temporarily unavailable.") from exc
    rows = getattr(result, "data", None)
    if isinstance(rows, list):
        rows = rows[0] if rows else None
    if not isinstance(rows, dict):
        raise HTTPException(status_code=503, detail="Admin request review returned an invalid response.")
    try:
        return {"data": AdminRequestReviewResult.model_validate(rows).model_dump(mode="json")}
    except ValidationError as exc:
        raise HTTPException(status_code=503, detail="Admin request review returned an invalid response.") from exc
