# Local setup

## Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Health: `http://localhost:8000/api/v1/health`. Add Supabase credentials only to `backend/.env`; never commit it or put the service role key in frontend configuration.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Database

The current backend requires the complete migration sequence, in this order:

`001_initial_schema.sql` → `002_align_oulad_schema.sql` → `003_account_approval.sql` → `004_latest_learner_data_views.sql` → `005_dataset_ownership.sql` → `006_master_admin_workspaces.sql` → `007_idempotent_model_predictions.sql`.

Migration 001 creates only the initial schema; it is not the complete schema required by the current backend. Review the migrations, target project identity, RLS policies, grants, and API authorization, and use the approved migration process for an isolated non-production environment before loading test data.

`database/proposals/phase4b_recommendation_idempotency.sql` is a separate proposal, not part of migrations 001–007. It requires independent review and explicit authorization before it is applied anywhere.
