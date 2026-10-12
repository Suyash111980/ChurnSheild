# ChurnShield API

FastAPI service for dashboard, learner, prediction, and retention workflows. Versioned routes use `/api/v1`.

## Run locally

From this directory, create a virtual environment, install requirements, copy `.env.example` to `.env`, then run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/v1/health`. Interactive docs: `/docs`. Supabase configuration is optional for health and required for protected database routes. Supabase handles sign-in and session issuance in the frontend; the API verifies its bearer access tokens. Keep `SUPABASE_SECRET_KEY` server-side and provide it only through the environment or this directory's ignored `.env` file.

## Configuration

`APP_ENV`, comma-separated `CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_ALGORITHM`, and `MODEL_PATH` load from environment or this directory's `.env`. The current project uses ES256; configure the exact Supabase Auth issuer for the selected project. The publishable key is not used by the backend database client.
