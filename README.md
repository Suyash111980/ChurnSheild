# ChurnShield

AI-powered learner churn prediction and retention intelligence. Repository components: React/Vite frontend, FastAPI backend, ML pipeline, PostgreSQL migrations, and shared documentation.

- `frontend/` — React dashboard and API client.
- `backend/` — FastAPI service under `/api/v1`.
- `ml/` — OULAD processing, feature engineering, training, inference, and explanations.
- `database/migrations/` — PostgreSQL schema history.
- `docs/` — architecture, API, data, model, and setup notes.

See [docs/setup-guide.md](docs/setup-guide.md). Never commit `.env` files, private learner data, or generated model artifacts. Shreya owns `ml/`, Suyesh owns `backend/` and `database/`, and Parth owns `frontend/`.
