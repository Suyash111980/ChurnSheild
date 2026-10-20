from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_roles
from app.api.routes import master_admin


class FakeQuery:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error

    def select(self, _columns):
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return self.tables[name]


def set_supabase(monkeypatch, tables, master_id="master-id"):
    monkeypatch.setattr(master_admin, "supabase", FakeSupabase(tables))
    monkeypatch.setattr(
        master_admin,
        "settings",
        SimpleNamespace(master_admin_user_id=master_id),
    )


def test_platform_overview_counts_platform_records_without_returning_rows(monkeypatch):
    set_supabase(
        monkeypatch,
        {
            "profiles": FakeQuery([
                {"id": "master-id", "role": "admin", "approval_status": "approved"},
                {"id": "pending-id", "role": "educator", "requested_role": "admin", "approval_status": "pending"},
                {"id": "approved-id", "role": "admin", "requested_role": "admin", "approval_status": "approved"},
                {"id": "denied-id", "role": "educator", "requested_role": "admin", "approval_status": "denied"},
            ]),
            "workspaces": FakeQuery([{"id": "workspace-1"}, {"id": "workspace-2"}]),
            "dataset_uploads": FakeQuery([
                {"id": "dataset-1", "status": "processed"},
                {"id": "dataset-2", "status": "failed"},
            ]),
        },
    )

    result = master_admin.platform_overview(_master={"app_role": "master_admin"})

    assert result == {
        "admin_accounts": 3,
        "pending_admin_requests": 1,
        "approved_admins": 1,
        "rejected_admins": 1,
        "workspaces": 2,
        "datasets": 2,
        "dataset_status_counts": {"processed": 1, "failed": 1},
    }


def test_platform_overview_returns_legitimate_empty_database_state(monkeypatch):
    set_supabase(monkeypatch, {name: FakeQuery([]) for name in ("profiles", "workspaces", "dataset_uploads")})

    result = master_admin.platform_overview(_master={"app_role": "master_admin"})

    assert result == {
        "admin_accounts": 0,
        "pending_admin_requests": 0,
        "approved_admins": 0,
        "rejected_admins": 0,
        "workspaces": 0,
        "datasets": 0,
        "dataset_status_counts": {},
    }


def test_platform_overview_keeps_database_errors_as_503_and_logs_safe_code(monkeypatch, caplog):
    missing_column = RuntimeError("database provider error")
    missing_column.code = "42703"
    set_supabase(
        monkeypatch,
        {
            "profiles": FakeQuery([], error=missing_column),
            "workspaces": FakeQuery([]),
            "dataset_uploads": FakeQuery([]),
        },
    )

    with pytest.raises(HTTPException) as error:
        master_admin.platform_overview(_master={"app_role": "master_admin"})

    assert error.value.status_code == 503
    assert "Verify deployed migrations" in error.value.detail
    assert "provider_code=42703" in caplog.text
    assert "database provider error" not in caplog.text


@pytest.mark.parametrize("role", ["admin", "retention_manager", "data_analyst"])
def test_non_master_roles_are_denied_by_platform_overview_dependency(role):
    dependency = require_roles("master_admin")

    with pytest.raises(HTTPException) as error:
        dependency(current_user={"app_role": role})

    assert error.value.status_code == 403


def test_master_admin_role_is_allowed_by_platform_overview_dependency():
    dependency = require_roles("master_admin")
    master = {"app_role": "master_admin"}

    assert dependency(current_user=master) == master
