from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "008_admin_request_history.sql"
)


def test_admin_request_audit_is_not_directly_exposed_to_client_roles():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "alter table public.admin_request_audit enable row level security" in sql
    assert "revoke all on public.admin_request_audit from public, anon, authenticated" in sql
    assert "grant select, insert on public.admin_request_audit to service_role" in sql


def test_admin_request_functions_are_fixed_path_and_service_role_only():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert sql.count("security definer\nset search_path = ''") >= 3
    assert "grant execute on function public.master_list_admin_requests" in sql
    assert "to service_role" in sql
    assert "grant execute on function public.record_admin_request_submission()" not in sql


def test_review_rpc_locks_pending_request_and_records_review_atomically():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "for update" in sql
    assert "decision is null or decision not in ('approve', 'reject')" in sql
    assert "status_filter is null or status_filter not in" in sql
    assert "target.approval_status is distinct from 'pending'" in sql
    assert "reviewed_by = reviewer_user_id" in sql
    assert "insert into public.admin_request_audit" in sql
    assert "create table if not exists public.admin_request_audit" in sql


def test_display_data_is_allowlisted_and_existing_access_is_not_auto_approved():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for allowed_field in ("'full_name'", "'name'", "'display_name'", "'username'", "u.email"):
        assert allowed_field in sql
    assert "update public.profiles" in sql
    assert "where p.requested_role = 'admin'" in sql
    assert "update public.profiles p set approval_status = 'approved'" not in sql
    assert "role = case when decision = 'approve' then 'admin' else role end" in sql

