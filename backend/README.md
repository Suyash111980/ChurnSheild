# ChurnShield API

FastAPI service for dashboard, learner, prediction, and retention workflows. Versioned routes use `/api/v1`.

## Run locally

From this directory, create a virtual environment, install requirements, copy `.env.example` to `.env`, then run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/v1/health`. Interactive docs: `/docs`. Supabase credentials are optional for health and required for database routes. Keep the service role key server-side.

## Configuration

`APP_ENV`, comma-separated `CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `MODEL_PATH` load from environment or this directory's `.env`.
