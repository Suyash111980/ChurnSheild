from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_authenticated_profile

router = APIRouter(prefix="/api/v1/auth", tags=["Account"])


@router.get("/status")
def account_status(current_profile: dict = Depends(get_authenticated_profile)):
    """Return the caller's own trusted role and approval state."""
    return {
        "id": current_profile["id"],
        "app_role": current_profile["app_role"],
        "approval_status": current_profile["approval_status"],
    }
