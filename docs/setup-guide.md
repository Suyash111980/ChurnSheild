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

Apply `database/migrations/001_initial_schema.sql` with your migration workflow or Supabase SQL editor. Review RLS policies and API authorization before loading real learner data.
