# Local setup

## Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --reload
```

If `.env` already exists, do not overwrite it when copying the example. Health: `http://localhost:8000/api/v1/health` works without Supabase, but authentication status, workspace, and dataset APIs require a configured backend Supabase project. Set `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `backend/.env`; the backend secret key must come from the project's administrator and must never go in the frontend. `SUPABASE_JWT_ISSUER` may be left blank to derive `<SUPABASE_URL>/auth/v1`. `SUPABASE_JWT_ALGORITHM` must match the project's asymmetric JWT signing key (`ES256` or `RS256`). Set `CORS_ORIGINS` to the exact frontend origin; local defaults allow `http://localhost:5173` and `http://localhost:5174`. Restart Uvicorn after changing backend configuration. Never commit `backend/.env`.

If startup logs list missing backend settings, check that `backend/.env` contains non-empty values for those exact variable names. The example file intentionally uses placeholders and is not a working project configuration. Never copy placeholder values into the local env files or share their secret values.

## Frontend

```powershell
cd frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` in `frontend/.env.local` from the same Supabase project as the backend. `VITE_API_BASE_URL` defaults to `http://localhost:8000/api/v1`. If Vite selects a port outside 5173/5174, add that exact origin to `CORS_ORIGINS` in `backend/.env` and restart both development servers.

## Database

The current backend requires the complete migration sequence, in this order:

`001_initial_schema.sql` → `002_align_oulad_schema.sql` → `003_account_approval.sql` → `004_latest_learner_data_views.sql` → `005_dataset_ownership.sql` → `006_master_admin_workspaces.sql` → `007_idempotent_model_predictions.sql`.

Migration 001 creates only the initial schema; it is not the complete schema required by the current backend. Review the migrations, target project identity, RLS policies, grants, and API authorization, and use the approved migration process for an isolated non-production environment before loading test data.

`database/proposals/phase4b_recommendation_idempotency.sql` is a separate proposal, not part of migrations 001–007. It requires independent review and explicit authorization before it is applied anywhere.

Dataset deletion additionally requires the reviewed policy in `database/migrations/008_dataset_delete_policy.sql`. It allows only an authenticated, approved Admin to delete a non-processing dataset in their active workspace. The delete runs with the user's JWT so RLS remains enforced; existing foreign keys cascade learner records, features, predictions, explanations, and recommendations in the same PostgreSQL transaction. The application does not apply this migration automatically. Until an administrator applies it through the project's normal migration process, the Delete Dataset action will be rejected by Supabase.
