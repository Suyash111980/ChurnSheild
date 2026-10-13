
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.learners import router as learners_router
from app.api.routes.account import router as account_router
from app.api.routes.admin_users import router as admin_users_router

app = FastAPI(
    title="ChurnShield API",
    description="AI-Powered Learner Churn Prediction & Retention Intelligence",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register API routers
app.include_router(learners_router)
app.include_router(account_router)
app.include_router(admin_users_router)


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "ChurnShield API", "status": "running"}


@app.get("/api/v1/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "churnshield-backend",
        "version": app.version,
    }
