from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies.datasets import require_admin_workspace, require_owned_dataset
from app.repositories import dataset_repository


class FakeQuery:
    def __init__(self, rows): self.rows, self.filters = rows, []
    def select(self, *_args, **_kwargs): return self
    def eq(self, field, value): self.filters.append((field, value)); return self
    def limit(self, _count): return self
    def execute(self):
        data = [row for row in self.rows if all(row.get(k) == v for k, v in self.filters)]
        return SimpleNamespace(data=data)


class FakeDb:
    def __init__(self, rows): self.rows, self.query = rows, None
    def table(self, name):
        self.query = FakeQuery(self.rows.get(name, [])); return self.query


def test_authenticated_admin_workspace_is_derived_from_database(monkeypatch):
    user_id, workspace_id = str(uuid4()), str(uuid4())
    db = FakeDb({"workspaces": [{"id": workspace_id, "admin_user_id": user_id, "status": "active"}]})
    monkeypatch.setattr(dataset_repository, "supabase", db)
    result = require_admin_workspace(user={"id": user_id, "app_role": "admin"})
    assert result["workspace_id"] == workspace_id
    assert db.query.filters == [("admin_user_id", user_id)]


def test_master_admin_workspace_is_still_scoped_to_its_own_identity(monkeypatch):
    user_id, workspace_id = str(uuid4()), str(uuid4())
    db = FakeDb({"workspaces": [{"id": workspace_id, "admin_user_id": user_id, "status": "active"}]})
    monkeypatch.setattr(dataset_repository, "supabase", db)
    result = require_admin_workspace(user={"id": user_id, "app_role": "master_admin"})
    assert result["workspace_id"] == workspace_id
    assert db.query.filters == [("admin_user_id", user_id)]


def test_missing_workspace_fails_closed(monkeypatch):
    user_id = str(uuid4())
    monkeypatch.setattr(dataset_repository, "supabase", FakeDb({"workspaces": []}))
    with pytest.raises(HTTPException) as error:
        require_admin_workspace(user={"id": user_id, "app_role": "admin"})
    assert error.value.status_code == 403


def test_workspace_lookup_failure_returns_503_and_logs_no_exception_detail(monkeypatch, caplog):
    class ProviderError(RuntimeError):
        code = "PGRST205"

    class BrokenDb:
        def table(self, _name):
            raise ProviderError("response included a private database detail")

    monkeypatch.setattr(dataset_repository, "supabase", BrokenDb())
    with pytest.raises(HTTPException) as error:
        require_admin_workspace(user={"id": str(uuid4()), "app_role": "admin"})

    assert error.value.status_code == 503
    assert "ProviderError" in caplog.text
    assert "PGRST205" in caplog.text
    assert "private database detail" not in caplog.text


def test_dataset_lookup_requires_authenticated_owner_and_workspace(monkeypatch):
    user_id, workspace_id, dataset_id = map(str, (uuid4(), uuid4(), uuid4()))
    db = FakeDb({"dataset_uploads": [{"id": dataset_id, "owner_id": user_id, "workspace_id": workspace_id}]})
    monkeypatch.setattr(dataset_repository, "supabase", db)
    row = dataset_repository.get_owned_dataset(dataset_id, user_id, workspace_id)
    assert row["id"] == dataset_id
    assert db.query.filters == [("id", dataset_id), ("owner_id", user_id), ("workspace_id", workspace_id)]


def test_forged_dataset_or_workspace_id_is_not_found(monkeypatch):
    user_id, workspace_id, other_workspace_id, dataset_id = map(str, (uuid4(), uuid4(), uuid4(), uuid4()))
    db = FakeDb({"dataset_uploads": [{"id": dataset_id, "owner_id": user_id, "workspace_id": other_workspace_id}]})
    monkeypatch.setattr(dataset_repository, "supabase", db)
    assert dataset_repository.get_owned_dataset(dataset_id, user_id, workspace_id) is None


def test_workspace_scoped_access_hides_other_admin_dataset(monkeypatch):
    user_id, workspace_id, other_workspace_id, dataset_id = map(str, (uuid4(), uuid4(), uuid4(), uuid4()))
    db = FakeDb({"dataset_uploads": [{"id": dataset_id, "owner_id": str(uuid4()), "workspace_id": other_workspace_id}]})
    monkeypatch.setattr(dataset_repository, "supabase", db)
    with pytest.raises(HTTPException) as error:
        require_owned_dataset(dataset_id=dataset_id, user={"id": user_id, "app_role": "admin", "workspace_id": workspace_id})
    assert error.value.status_code == 404
