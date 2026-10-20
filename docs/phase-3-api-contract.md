# Phase 3 API and integration contract

All application APIs require a valid Supabase bearer token and an approved ChurnShield profile. JWT verification includes signature, issuer, audience, expiry, and subject. The only supported application roles are `admin` and the configured `master_admin` overlay. Existing database `educator` and `analyst` values are not mapped to application roles; approved profiles with those values are denied. Pending legacy `educator` profiles may read their own approval status. The database constraints and existing records are unchanged. The backend uses a privileged Supabase client, so every dataset read and write is owner-filtered in backend code.

## Dataset workflow

- `POST /api/v1/datasets/preview` accepts multipart `file`; `POST /api/v1/datasets/upload` accepts `file` and optional `dataset_name`. Both are Admin-only. Upload parses CSV/XLSX in bounded memory, validates content and columns, stores learner and feature rows, and attempts inference only if columns match the versioned contract, the saved artifact is available, and `MODEL_APPROVED_VERSION` exactly matches the artifact metadata. Inference stays disabled when that setting is empty.
- `GET /api/v1/datasets` and `GET /api/v1/datasets/{dataset_id}` list and read only the authenticated owner's datasets. These are available to both supported approved roles.
- `POST /api/v1/datasets/{dataset_id}/retry` is Admin-only and requires re-uploading the file because raw uploads are not retained.
- Per-file limits are 25 MiB, 100,000 data rows, and 100 columns. The API reports descriptive compatibility separately from model compatibility. A compatible file is not silently scored if its artifact is missing.
- Upload processing is currently synchronous. The response reports the dataset status and validation data; status tracking is persisted. Temporary bytes are kept only in request memory.

All learner and prediction operations require `dataset_id` as a query parameter and an owned, processed dataset. Paginated responses use `data`, `limit`, `offset`, `count`, `total`, and `has_more`.

## Learners, predictions, and explanations

- `GET /api/v1/learners` supports `id_student`, `code_module`, `code_presentation`, and `risk_category` filters. Pagination and filters run in the database.
- `GET /api/v1/learners/{learner_id}?dataset_id=...` uses the database UUID and returns the learner, optional display name, latest feature snapshot and prediction, persisted explanations, and persisted recommendations.
- Prediction list, detail, learner history, and explanation routes are read-only and scoped to the dataset. Explanations are selected only after verifying that the prediction belongs to a learner in that dataset.
- Upload processing persists model predictions when available. SHAP is a best-effort local capability only; explanation rows are not currently persisted by the upload flow, so APIs return empty explanations unless records already exist.

## Dashboard, early warning, analytics, exports

- `GET /api/v1/dashboard/summary?dataset_id=...` reports genuine persisted learner/course counts, prediction coverage, and risk counts. Risk distribution is `null` when no predictions exist.
- `GET /api/v1/early-warning?dataset_id=...` returns actual latest predictions and available evidence. Rows without predictions retain null risk values and are not treated as high risk.
- `GET /api/v1/analytics/model-evaluation` serves the saved held-out evaluation report and metadata; it does not calculate evaluation metrics from operational dataset predictions. Backend upload inference remains fail-closed until the exact artifact version is explicitly configured with `MODEL_APPROVED_VERSION`.
- `GET /api/v1/reports/learners.csv?dataset_id=...` exports up to 10,000 persisted learner rows with spreadsheet-formula escaping.

## Recommendations

- `GET /api/v1/recommendations?dataset_id=...` returns only persisted rows. Generation is not implemented.
- `PATCH /api/v1/recommendations/{recommendation_id}?dataset_id=...` allows Admin only. The conditional mutation repeats the learner foreign-key scope established by the dataset-scoped lookup. Valid transitions are `pending → in_progress|dismissed` and `in_progress → completed|dismissed`; terminal states cannot be reopened. Repeating the current state is idempotent; concurrent changes return 409.

## Canonical OULAD model contract

The shared contract is [oulad-learner-v1.json](../ml/schemas/oulad-learner-v1.json). Input identifiers are `id_student`, `code_module`, and `code_presentation`; model features exclude identifiers, target, final outcome, post-cutoff registration data, and demographic/protected attributes. The target is `target_withdrawn=1` for Withdrawn, and `0` for Pass, Fail, or Distinction. The target cutoff follows the project's provisional day-30 proposal.

Risk bands are provisional: low `<0.30`, medium `0.30–<0.70`, high `≥0.70`. They are separate from the model's baseline 0.50 classification threshold. They require stakeholder and operational validation before deployment.

The optional student display CSV is configured by `STUDENT_DISPLAY_CSV_PATH`; missing or conflicting names resolve to `null`. Such labels are not verified identities, authorization keys, or model features.

## Database rollout and legacy records

Migrations `004_latest_learner_data_views.sql`, `005_dataset_ownership.sql`, `006_master_admin_workspaces.sql`, and `007_idempotent_model_predictions.sql` have been created but **not applied**. Review and deploy them in that order only through the approved Supabase migration process. Migration 005 leaves old dataset ownership and learner `dataset_id` values null; migration 006 leaves historical workspace links unassigned; no ownership is guessed or backfilled. Such legacy rows are not visible through the dataset-scoped application APIs. Review SQL against the target Supabase version before applying, and plan a separately approved legacy ownership procedure if those rows must be retained in a workspace.

The Master Admin is intentionally provisioned without a customer workspace. Consequently, the current Admin workspace upload endpoints cannot be used by Master Admin to import a platform OULAD dataset. Supporting that workflow requires an explicit workspace-selection/ownership design; do not create a Master Admin workspace or bypass owner checks as a workaround.

The database schema and live Supabase connectivity were not exercised. Full upload-to-frontend verification needs the reviewed migrations deployed to a non-production Supabase project with test data and the configured model artifact.
