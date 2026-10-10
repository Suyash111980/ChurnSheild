# System architecture

The React/Vite frontend uses JSON REST endpoints under `/api/v1`. FastAPI handles authorization, persistence, model inference, explanations, recommendations, and reporting. The backend loads versioned model artifacts created by `ml/`; browsers never load model files. Supabase PostgreSQL stores learner-course records and intervention workflow data.

Training and serving must share an explicit feature schema. Features may use only information available at the prediction date; `final_result` is a target and must never be an input.
