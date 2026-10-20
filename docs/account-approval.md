# Master Admin approval and workspace bootstrap

## Migration review and deployment order

Review and deploy the complete migration chain in order: **001 → 002 → 003 → 004 → 005 → 006 → 007** (`001_initial_schema.sql`, `002_align_oulad_schema.sql`, `003_account_approval.sql`, `004_latest_learner_data_views.sql`, `005_dataset_ownership.sql`, `006_master_admin_workspaces.sql`, and `007_idempotent_model_predictions.sql`). Migration 001 creates only the initial schema; it is not the complete schema required by the current backend. Migration 006 records an Admin request from signup metadata but always creates a pending `educator` profile; metadata never grants a role or approval. It adds a one-to-one Admin workspace, a dataset workspace foreign key, and a service-role-only transaction for approval/rejection. It does not assign historical datasets or learner rows to a workspace. Migration 007 adds the learner/model prediction uniqueness contract and stops on duplicates for manual review. No migration has been applied by this implementation.

`database/proposals/phase4b_recommendation_idempotency.sql` is a separate proposal, not part of migrations 001–007. It requires independent schema/data review and explicit authorization before any deployment.

Before deployment, review the `security definer` functions, grants, RLS behavior, existing triggers, historical `NULL` owner/dataset/workspace rows, and the fact that datasets created before migration 006 have no workspace. Run migrations only through the project's controlled migration process after database review.

## Designating the Master Admin

There is no public Master Admin creation endpoint. Bootstrap requires a trusted operator:

1. Create or verify the owner's account using Supabase Auth and independently verify the Auth UUID.
2. Through a trusted database operator session, ensure that UUID has a profile with `role='admin'` and `approval_status='approved'`. Do not use signup metadata to do this.
3. Configure the backend-only `MASTER_ADMIN_USER_ID` environment variable with that verified UUID. Never set it in frontend/Vite variables.
4. Sign in and verify `/api/v1/auth/status` reports `app_role: master_admin`. Backend elevation is granted only when the verified JWT subject matches the configured UUID and the trusted profile is approved with role `admin`.

The Master Admin has platform-management access, not an Admin customer workspace. Keep this UUID configuration controlled and reviewed. If the designated account changes, update the server configuration through the secret-management process and verify access before removing the old designation.

## Admin request flow

The signup UI lets a person explicitly request an Admin workspace. When selected, it sends `requested_role=admin`; migration 006's Auth trigger stores that only in `profiles.requested_role`. Public signup metadata never sets `profiles.role` or `approval_status`. Every new account starts as `educator/pending`, with no workspace. Only the configured Master Admin can list Admin requests and review them. Approval invokes one transaction that sets `role=admin`, marks the profile approved, and creates exactly one workspace. Repeating approval returns the same workspace. Rejection marks the account denied. Legacy account approval endpoints use this Master Admin gate.

An account that does not request an Admin workspace also remains `educator/pending`. The current approval queue contains only explicit Admin requests, so there is no supported application flow to approve such a signup. Do not approve it by changing metadata or granting a role implicitly. Product owners must decide whether non-Admin signups should be disabled, offered a future supported role/onboarding path, or remain pending without application access. Until that decision is made, only explicitly requested Admin accounts can enter the approval workflow.

Legacy `educator`/`analyst` profiles remain represented for compatibility but do not receive workspace access in this workflow. No additional Retention Manager or Analyst approval queue is introduced.

The supported application roles are `admin` and the configured `master_admin` overlay. Approved legacy `educator` and `analyst` rows are not mapped to either role and are denied application access. Keep their records unchanged. Before any role migration or account remediation, inventory the affected accounts, confirm identity and intended access with account owners, define a reviewed remediation plan, and obtain approval for any schema or data change. Never infer a role from historical activity or signup metadata.

## Historical records

Migration 006 does not backfill existing accounts or datasets. Existing approved Admins do not automatically receive workspaces, and existing datasets with no `workspace_id` remain inaccessible through Admin workspace APIs. Inventory accounts and uploads, verify ownership with the responsible users, and perform a reviewed, explicit reconciliation before assigning workspaces. Never attach ambiguous records to the first Admin or to the Master Admin. Leave records unassigned until they can be attributed safely.

## Reference OULAD data

The Master Admin OULAD page reads the prepared local file under `ml/data/processed` and local model metadata/evaluation artifacts. It labels this as local reference data and reports `imported_to_supabase=false`; it does not upload it. Normal Admins have no route to the platform-level OULAD API or held-out evaluation endpoint. A future OULAD import must be an explicit, reviewed dataset operation scoped to a chosen Admin workspace.
