# ChurnShield API

FastAPI service for authenticated, dataset-scoped learner, prediction, dashboard, upload, analytics, and retention workflows. Versioned routes use `/api/v1`.

## Run locally

From this directory, create a virtual environment, install requirements, copy `.env.example` to `.env`, then run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/v1/health`. Interactive docs: `/docs`. Supabase configuration is optional for health and required for protected routes. Supabase handles sign-in and session issuance in the frontend; the API verifies bearer tokens and resolves approved profiles and roles. Dataset reads and writes always require an owned dataset; Admin-only endpoints accept uploads and retries. Do not expose `SUPABASE_SECRET_KEY` to the browser.

## Configuration

`APP_ENV`, comma-separated `CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_ALGORITHM`, `MASTER_ADMIN_USER_ID`, `MODEL_PATH`, `MODEL_APPROVED_VERSION`, and `STUDENT_DISPLAY_CSV_PATH` load from environment or this directory's ignored `.env`. Configure the signing algorithm and issuer to match the Supabase project's Auth settings. The publishable key is not used by the backend privileged database client. The optional display CSV is presentation metadata; when missing, learner APIs return `student_name: null`. Set `MASTER_ADMIN_USER_ID` only to the independently verified UUID of the approved, trusted Admin account designated as Master Admin; never place this setting in a frontend/Vite environment file.

Backend inference is disabled unless `MODEL_APPROVED_VERSION` exactly matches the `model_version` in the configured artifact's metadata sidecar. Leave it empty until the model target, cutoff, evaluation, and intended operational use have been approved. This prevents the legacy all-outcome artifact or provisional Day-30 candidate from being selected implicitly.

## Dataset workflow and deployment

`POST /api/v1/datasets/preview` validates and previews bounded CSV/XLSX content. Admin-only `POST /api/v1/datasets/upload` validates and processes it synchronously; it persists dataset-scoped learner and feature rows and creates predictions only when the file matches the shared ML contract and a compatible artifact is present. Upload bytes are not retained, so retries require a new upload. Dataset IDs are required for analytics and learner-related APIs. See [`../docs/phase-3-api-contract.md`](../docs/phase-3-api-contract.md) for request contracts and limitations.

Before deploying dataset and prediction routes, review the complete dependency chain `004_latest_learner_data_views.sql` → `005_dataset_ownership.sql` → `006_master_admin_workspaces.sql` → `007_idempotent_model_predictions.sql`, then deploy each through the approved database process. Migration 006 is required because workspace authorization queries `public.workspaces` and dataset queries select `workspace_id`; migration 007 is required for the prediction upsert conflict target. These migrations have not been applied by the local implementation. Legacy rows stay unowned and are intentionally hidden from dataset-scoped APIs until an approved ownership plan exists.

## Local checks

From `backend/`, run `python -m pytest tests -q --ignore=test_supabase_connection.py`. Tests use mocks and do not need a live database. ML checks from the repository root are `python -m pytest ml/tests -q`.
