# Database and migration deployment

## Migration inventory and order

The complete schema expected by the current backend is the numbered sequence below. Review and reconcile the target schema and migration history before selecting any files to deploy; the number order alone is not proof that a target is fresh or that any migration has been applied.

1. `migrations/001_initial_schema.sql` — initial learner, feature, prediction, explanation, recommendation, upload, and profile tables, indexes, RLS enablement, and own-profile read policy.
2. `migrations/002_align_oulad_schema.sql` — OULAD profile columns and compatibility creation of the data tables, indexes, and RLS setup.
3. `migrations/003_account_approval.sql` — approval status and the Auth-user profile trigger.
4. `migrations/004_latest_learner_data_views.sql` — latest prediction, feature, and recommendation views.
5. `migrations/005_dataset_ownership.sql` — upload ownership and processing metadata, dataset-scoped learner identity, dataset/dashboard views, and owner-scoped policies.
6. `migrations/006_master_admin_workspaces.sql` — Admin request metadata, workspaces, approval RPC, workspace validation trigger, and workspace-scoped policies.
7. `migrations/007_idempotent_model_predictions.sql` — non-null and unique `(learner_id, model_version)` prediction identity, after duplicate preflight.

Migration 001 is only the initial schema. It does not provide the dataset ownership, workspace, processing, dashboard-summary, or prediction-upsert contract used by the current backend. `IF NOT EXISTS` avoids some duplicate-object errors; it does not reconcile an existing object with the required columns, types, constraints, index definition, grants, or policies.

The current repository stores these plain SQL files in `database/migrations/` with numeric prefixes. There is no checked-in `supabase/config.toml` or CLI migration directory. Supabase CLI migration tracking normally uses timestamped files under `supabase/migrations/` and the remote `supabase_migrations.schema_migrations` history. The CLI compares local migration versions with that history; it does not infer that these numbered files are deployed from their names or from existing tables. Do not create a competing history table or run `supabase db push` against this directory as-is. First review and approve a packaging/history-reconciliation approach for these exact SQL files. See [Supabase database migrations](https://supabase.com/docs/guides/deployment/database-migrations), [`supabase migration list`](https://supabase.com/docs/reference/cli/supabase-migration-list), and [`supabase db push`](https://supabase.com/docs/reference/cli/supabase-db-push).

## Supabase prerequisites

The migrations expect a Supabase PostgreSQL project with the platform-provided `auth.users`, `auth.uid()`, `anon`, `authenticated`, `service_role`, and `supabase_auth_admin` objects/roles, and `pgcrypto` available to the migration identity. The SQL references these platform objects directly. Confirm the target PostgreSQL version supports the `security_invoker` view option used by migrations 004 and 005. Confirm the deployment identity is explicitly authorized to create/alter public objects, policies, functions, triggers, grants, and Auth triggers; never substitute the application service-role key for migration authorization.

Migration 001's profile role check allows legacy values `admin`, `educator`, and `analyst`; migration 006 does not rewrite that constraint. The application recognizes `admin` and derives `master_admin` only for the configured, approved Admin identity. New signups remain pending educator profiles with an optional Admin request; public signup metadata cannot approve an account or grant either application role. Do not remove or remap legacy role values as part of this migration sequence.

Before a staging deployment, independently confirm the project reference in the Supabase dashboard and compare it with the linked CLI project. The intended staging reference must be explicitly confirmed by the operator; a matching project reference alone does not prove the schema is safe to change. Confirm the project URL/reference, database identity, environment label, access role, migration source directory, and absence of a production fallback. Abort on missing, malformed, conflicting, or ambiguous target details. Do not print credentials or credential-bearing URLs.

## Required preflight by migration

### Before 005

- Confirm 001–004 are applied and compatible with the deployed definitions; specifically confirm all seven base tables exist, `learners_latest_prediction` exists with the expected columns/types/order, and the feature/recommendation views and required grants are present.
- Verify `dataset_uploads.id`, `filename`, `status`, and `uploaded_at` types/nullability. Migration 005 derives a missing `dataset_name` from `filename`; confirm filenames are present and meaningful, existing non-null dataset names are valid, and every existing status fits the new allowed set (`uploaded`, `validated`, `processing`, `processed`, `failed`). Do not treat a failed check constraint as an invitation to normalize data automatically.
- Verify all existing/newly present ownership and processing columns have compatible types and constraints. `ADD COLUMN IF NOT EXISTS` does not validate a pre-existing same-named column.
- Confirm exactly one supported learner identifier is present: non-null text `external_learner_id`, or the legacy `id_student` column that this migration renames. If both exist, stop for manual reconciliation; do not choose one or merge values automatically. Verify non-null text `code_module` and `code_presentation`.
- Count duplicate `(dataset_id, external_learner_id, code_module, code_presentation)` groups before proceeding. Review the old global learner uniqueness constraint and every dependent object before its removal/replacement. Migration 005 aborts on duplicate groups and does not delete/merge learners.
- Inspect every index name created by 005 (`learners_legacy_source_unique`, `dataset_uploads_owner_uploaded_idx`, `learners_dataset_course_idx`, `learner_features_learner_snapshot_idx`, and `recommendations_learner_created_idx`) for its exact table, ordered keys, uniqueness, predicate, validity, and included columns. `CREATE INDEX IF NOT EXISTS` does not verify a same-named index definition.
- Record counts of uploads with null ownership and learners with null `dataset_id`. These remain unassigned; the migration does not infer owners or datasets. Confirm all resulting unassigned rows must remain inaccessible through workspace APIs until separately reconciled.
- Inventory every existing RLS policy and grant on protected tables. PostgreSQL permissive policies can combine with OR semantics; unknown pre-existing broad policies must be resolved by an authorized schema review before relying on the new owner policies.

### Before 006

- Verify 005 is applied and inspect `profiles.id`, `role`, `approval_status`, `requested_role`, and `created_at`, plus `dataset_uploads.owner_id` and `dataset_id` and their exact types/constraints.
- Verify the Auth trigger/function name, owner, `SECURITY DEFINER` status, fixed `search_path`, trigger attachment, and `supabase_auth_admin` execute grant. Verify `master_review_admin_request(uuid,text)` definition and that execute is granted only to `service_role` among API roles.
- Inspect `public.workspaces` if it already exists. `CREATE TABLE IF NOT EXISTS` does not reconcile its schema. Confirm its unique one-workspace-per-Admin key, profile foreign key, status constraint, RLS, grants, and owner policy before proceeding.
- Inspect existing `dataset_uploads_workspace_uploaded_idx` and `dataset_uploads_id_workspace_unique` definitions, and verify the `workspace_id` foreign key. The migration's `ADD COLUMN IF NOT EXISTS` does not add a missing FK to an already-present column.
- Count approved Admin profiles without a workspace and uploads without `workspace_id`; count any non-null owner/workspace mismatches. Migration 006 deliberately does not backfill workspaces or assign ownership. Do not auto-approve profiles, change roles, or invent historical mappings.
- Review all policies on workspaces, uploads, learners, features, predictions, explanations, and recommendations. Verify the dataset ownership chain and application query filters. The backend uses a privileged server-side Supabase client that can bypass RLS, so RLS alone does not prove API workspace isolation.

### Before 007

- Verify `predictions.learner_id` is UUID, `model_version` is text/varchar, and `created_at` has the intended timestamp type; verify learner foreign keys and the backend upsert conflict target.
- Count null values in all three columns and duplicate `(learner_id, model_version)` groups. Migration 007 aborts if nulls or duplicates exist. It does not delete, merge, or select a winning historical prediction.
- If `predictions_learner_model_unique` already exists, verify it is on `public.predictions`, unique, valid, ready, non-partial, without expressions or included columns, and has exactly ordered keys `(learner_id, model_version)`. Do not accept a same-named index based on its name alone.

Migration 007 is a separate integrity change from workspace repair. The backend prediction writer uses `on_conflict="learner_id,model_version"`; that write contract depends on the matching unique index.

## Data preservation, transaction behavior, and recovery

Migrations 002, 005, 006, and 007 declare transaction boundaries. Migration 001 and 003 do not wrap their statements in an explicit transaction. Migration 001's profile policy creation is unguarded; migration 005's additional named check constraints are not all guarded for repeat execution; and `IF NOT EXISTS` in 005/006 does not verify existing column, table, foreign-key, or index definitions. Migration 006's approval RPC uses conflict handling to avoid duplicate workspaces, but that does not make replaying the DDL a safe schema reconciliation strategy. A migration history entry should be recorded only after the corresponding migration completes successfully under the chosen deployment mechanism. Inspect for partial/manual application before retrying any file; do not infer success from a subset of its objects.

Migrations 005 and 007 contain data-dependent checks and may abort on incompatible schema or rows. Migration 005 copies `filename` into missing `dataset_name`, renames legacy `id_student` when it is the sole source-ID column, drops the old global learner uniqueness constraint, and adds dataset-scoped uniqueness. These changes do not delete learner rows. Migration 006 adds cascading foreign keys: deleting an Auth profile can cascade through its workspace, uploads, and dataset-linked learners. It creates workspaces only when the Admin request is explicitly approved through its service-role RPC; it does not backfill existing Admins or datasets. These retention consequences require operator review. Migration 007 does not remove/merge prediction history.

Before any DDL, confirm a recent recoverable backup/PITR point, who can restore it, the recovery objective, and a tested restoration procedure for the target. Transaction rollback protects a failed transaction, not a later operational rollback after committed schema/data changes. Dropped constraints, renamed columns, changed triggers/policies, and committed updates require a forward repair or point-in-time restore; do not promise a simple reverse migration. Schedule a maintenance window and capture pre-deployment schema/history evidence and aggregate data counts.

## Staging-only procedure — proposed, not executed

**This is a gated procedure, not authorization to deploy.** The current repository is not yet a Supabase CLI migration project, so these commands are not executable safely until a separately reviewed change maps the numbered SQL files to timestamped CLI migration files without changing their contents or inventing history. Do not copy or rename files ad hoc.

After that packaging/history plan is reviewed, an operator with separate staging authorization may use this sequence from the approved CLI project directory. The `link` step changes local CLI project-link state and requires its own approval. Confirm the project reference against the dashboard immediately before continuing; stop on any mismatch.

```powershell
# PROPOSED ONLY — establishes the explicit staging link; changes local CLI state.
supabase link --project-ref cpbzjxmvfuqhhwtckggl

# PROPOSED ONLY — remote read-only migration-history comparison.
supabase migration list --linked

# PROPOSED ONLY — contacts linked staging and reports pending migrations; does not apply them.
supabase db push --linked --dry-run

# NOT AUTHORIZED BY THIS PLAN — run only after separate explicit deployment approval,
# reviewed history/schema/data preflights, recovery confirmation, and dry-run sign-off.
supabase db push --linked
```

Do not use `--include-all`, `migration repair`, `--db-url`, a production-linked checkout, or the application service-role credential to force alignment. If the numbered files cannot be safely reconciled to the CLI history, stop and prepare a schema-specific forward-repair proposal for independent review; do not replay migrations blindly. A dry run is not a substitute for catalog review or a verified target.

### Deployment blockers

Do not deploy while any of these remain unresolved:

- Staging project identity, CLI link, database identity, migration runner, or migration-history state is ambiguous.
- Actual schema differs from the expected predecessor contract, an object exists with incompatible shape, or migrations are partially applied.
- Migration 005 filename/status/learner-key/duplicate preflights fail, or ownership attribution is being assumed.
- Migration 006 workspace/schema/policy/grant checks fail, or historical ownership/workspace links need decisions.
- Migration 007 null/duplicate/index-definition checks fail.
- Existing permissive RLS policies, grants, function ownership/search paths, or service-role application filters have not been reviewed.
- Same-named indexes, constraints, views, functions, triggers, or columns have not been checked for their exact expected definitions.
- Backup/PITR and recovery ownership are unconfirmed, or the operator lacks explicit staging deployment authorization.

After an approved deployment, read back the migration history, compare object definitions and grants/policies against reviewed expectations, confirm row counts and null-ownership counts have not changed unexpectedly, verify a newly approved Admin receives exactly one workspace, verify trusted upload ownership/workspace validation, and test cross-workspace denial at both API and database-client boundaries. Keep unassigned historical records unassigned unless a separately approved attribution procedure exists.

## Separate recommendation idempotency proposal

`proposals/phase4b_recommendation_idempotency.sql` is a manual-review proposal, not migration 008 and not part of 001–007. The current recommendation writer uses the `(prediction_id, rule_id)` conflict target and performs dataset-scoped readback, so that recommendation path requires the proposed `rule_id` column and matching unique index before it can persist idempotently. The proposal is not required to restore dataset/workspace lookup or the base prediction upsert contract. Review its foreign keys, nullable historical behavior, duplicate preflight, index semantics, grants/RLS, and PostgreSQL compatibility independently; apply only after separate explicit authorization. It has not been included in the deployment command sequence above.

## Current evidence status

The checked-in migrations and backend source define the expected contracts; the local disposable PostgreSQL harness is compatibility evidence only and is not a deployed-schema inspection. No conclusion about which migrations are deployed, whether staging or production matches these definitions, or whether their data preflights pass is established by this README. Treat deployed schema/history, policy/grant state, RLS behavior, and all remote data counts as **unverified** until obtained through an authorized, target-verified inspection.

No migration has been applied to a live Supabase instance by the local implementation workflow. No learner rows are included in Git.
