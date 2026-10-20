from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "database" / "migrations" / "006_master_admin_workspaces.sql"


def test_signup_metadata_records_request_without_granting_role_or_approval():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "new.raw_user_meta_data ->> 'requested_role' = 'admin'" in sql
    assert "values (\n        new.id,\n        'educator',\n        'pending'" in sql
    assert "create table if not exists public.workspaces" in sql


def test_approval_is_transactional_workspace_unique_and_service_role_only():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "admin_user_id uuid not null unique" in sql
    assert "master_review_admin_request" in sql
    assert "on conflict (admin_user_id) do nothing" in sql
    assert "grant execute on function public.master_review_admin_request(uuid, text) to service_role" in sql
    assert "revoke all on function public.master_review_admin_request(uuid, text) from public, anon, authenticated" in sql


def test_migration_leaves_historical_records_unassigned():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column if not exists workspace_id uuid references public.workspaces" in sql
    assert "update public.dataset_uploads" not in sql
    assert "update public.learners" not in sql
