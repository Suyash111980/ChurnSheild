# Initial API contract

Base path: `/api/v1`; JSON fields use snake_case.

## Health

`GET /api/v1/health` returns `{"status":"healthy","service":"churnshield-backend","version":"0.1.0"}` without requiring a database connection.

Dataset, course, and report contracts will be documented alongside their route implementations. Authenticate and authorize users before exposing learner records.

Phase 3 learner, prediction, recommendation, and early-warning contracts are documented in [phase-3-api-contract.md](phase-3-api-contract.md).
