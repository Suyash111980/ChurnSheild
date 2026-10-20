from pathlib import Path

import pytest


MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"


def test_dataset_migration_uses_deployed_identifier_and_dataset_scoped_key():
    sql = (MIGRATIONS / "005_dataset_ownership.sql").read_text(encoding="utf-8").lower()

    assert "migration 005 requires dataset_uploads.id uuid" in sql
    assert "dataset_uploads processing metadata has an incompatible type" in sql
    assert "blank filename or unsupported status" in sql
    assert "existing blank names" in sql
    assert sql.index("detect source-key duplicates before the first ddl") < sql.index(
        "alter table public.dataset_uploads"
    )
    assert "migration 005 requires exactly one learner source-id column" in sql
    assert "existing dataset_uploads.owner_id must reference auth.users(id) with on delete cascade" in sql
    assert "existing learners.dataset_id must reference dataset_uploads(id) with on delete cascade" in sql
    assert "external_learner_id" in sql
    assert "rename column id_student to external_learner_id" in sql
    assert "unique (dataset_id, external_learner_id, code_module, code_presentation)" in sql
    assert "where dataset_id is null" in sql
    assert "update public.learners" not in sql
    assert "update public.dataset_uploads\nset dataset_name = filename" in sql
    assert "learner.external_learner_id" in sql


def test_workspace_migration_keeps_workspace_and_dependent_data_scoped():
    sql = (MIGRATIONS / "006_master_admin_workspaces.sql").read_text(encoding="utf-8").lower()

    assert "on conflict (admin_user_id) do nothing" in sql
    assert "p.role = 'admin'" in sql
    assert "p.approval_status = 'approved'" in sql
    assert "w.status = 'active'" in sql
    for policy in (
        "learners_select_dataset_owner",
        "learner_features_select_dataset_owner",
        "predictions_select_dataset_owner",
        "risk_explanations_select_dataset_owner",
        "recommendations_select_dataset_owner",
    ):
        assert f"create policy {policy}" in sql
    assert "grant execute on function public.master_review_admin_request(uuid, text) to service_role" in sql


def test_prediction_migration_rejects_unkeyable_rows_and_matches_writer_key():
    sql = (MIGRATIONS / "007_idempotent_model_predictions.sql").read_text(encoding="utf-8").lower()
    repo = (Path(__file__).resolve().parents[1] / "app" / "repositories" / "dataset_repository.py").read_text(encoding="utf-8").lower()

    assert "where learner_id is null" in sql
    assert "where model_version is null" in sql
    assert "where created_at is null" in sql
    assert "group by learner_id, model_version" in sql
    assert "on public.predictions (learner_id, model_version)" in sql
    assert '.upsert(records, on_conflict="learner_id,model_version")' in repo


def test_prediction_migration_accepts_only_the_expected_index_shape():
    sql = (MIGRATIONS / "007_idempotent_model_predictions.sql").read_text(encoding="utf-8").lower()

    assert "predictions_oid oid := to_regclass('public.predictions')" in sql
    assert "i.indrelid" in sql
    assert "array['learner_id', 'model_version']::text[]" in sql
    assert "predictions_learner_model_unique exists with an unexpected definition" in sql


@pytest.mark.parametrize(
    ("invalid_definition", "guard"),
    [
        ("same-named index on another table", "index_table_oid is distinct from predictions_oid"),
        ("non-unique index", "index_is_unique is distinct from true"),
        ("invalid index", "index_is_valid is distinct from true"),
        ("index not ready", "index_is_ready is distinct from true"),
        ("partial index", "index_is_partial is distinct from false"),
        ("unexpected included column", "index_has_included_columns is distinct from false"),
        ("expression index", "index_has_expressions is distinct from false"),
        (
            "unexpected key order or columns",
            "indexed_columns is distinct from array['learner_id', 'model_version']::text[]",
        ),
    ],
)
def test_prediction_migration_rejects_unsafe_existing_index_definitions(
    invalid_definition, guard
):
    sql = (MIGRATIONS / "007_idempotent_model_predictions.sql").read_text(encoding="utf-8").lower()

    assert guard.lower() in sql, invalid_definition

