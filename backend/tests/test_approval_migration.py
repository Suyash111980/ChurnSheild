from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "database"
    / "migrations"
    / "003_account_approval.sql"
)


def test_signup_trigger_uses_fixed_pending_educator_profile():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "add column if not exists approval_status text;" in sql
    assert "values (new.id, 'educator', 'pending')" in sql
    assert "new.raw_user_meta_data" not in sql
    assert "default 'pending'" not in sql
    assert "on auth.users" in sql


def test_migration_does_not_backfill_existing_profiles():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "update public.profiles" not in sql
