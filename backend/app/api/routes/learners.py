
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import require_roles
from app.integrations.supabase_client import supabase

router = APIRouter(prefix="/api/v1/learners", tags=["Learners"])


@router.get("")
def get_learners(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(
        require_roles("admin", "retention_manager", "data_analyst")
    ),
):
    if supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Database service is not configured.",
        )

    try:
        response = (
            supabase.table("learners")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return {
            "data": response.data,
            "limit": limit,
            "offset": offset,
            "count": len(response.data),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve learners from the database.",
        ) from exc
