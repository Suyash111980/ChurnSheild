from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes import admin_users
from app.main import app


PENDING_ID = str(uuid4())


class FakeProfilesQuery:
    def __init__(self):
        self.rows = [
            {
                "id": PENDING_ID,
                "role": "educator",
                "approval_status": "pending",
                "created_at": "2026-10-13T00:00:00Z",
            }
        ]
        self.filters = []
        self.updates = None
        self.selected = None

    def table(self, table_name):
        assert table_name == "profiles"
        return self

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column):
        assert column == "created_at"
        return self

    def update(self, values):
        self.updates = values
        return self

    def execute(self):
        if self.updates is None:
            return SimpleNamespace(data=self.rows)
        if self.filters == [
            ("id", PENDING_ID),
            ("approval_status", "pending"),
        ]:
            result = {
                "id": PENDING_ID,
                "role": self.updates.get("role", "educator"),
                "approval_status": self.updates["approval_status"],
            }
            return SimpleNamespace(data=[result])
        return SimpleNamespace(data=[])


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_pending_users_are_listed_for_admin(monkeypatch):
    fake_profiles = FakeProfilesQuery()
    monkeypatch.setattr(admin_users, "supabase", fake_profiles)
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}

    response = TestClient(app).get("/api/v1/admin/pending-users")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == PENDING_ID
    assert fake_profiles.filters == [("approval_status", "pending")]


def test_pending_user_list_is_admin_only(monkeypatch):
    monkeypatch.setattr(admin_users, "supabase", FakeProfilesQuery())
    app.dependency_overrides[get_current_user] = lambda: {
        "app_role": "retention_manager"
    }

    response = TestClient(app).get("/api/v1/admin/pending-users")

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("app_role", "database_role"),
    [
        ("admin", "admin"),
        ("retention_manager", "educator"),
        ("data_analyst", "analyst"),
    ],
)
def test_admin_approval_assigns_mapped_role(monkeypatch, app_role, database_role):
    fake_profiles = FakeProfilesQuery()
    monkeypatch.setattr(admin_users, "supabase", fake_profiles)
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}

    response = TestClient(app).patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"approval_status": "approved", "role": app_role},
    )

    assert response.status_code == 200
    assert fake_profiles.updates == {
        "approval_status": "approved",
        "role": database_role,
    }
    assert response.json()["data"]["role"] == database_role


def test_admin_can_deny_without_changing_role(monkeypatch):
    fake_profiles = FakeProfilesQuery()
    monkeypatch.setattr(admin_users, "supabase", fake_profiles)
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}

    response = TestClient(app).patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"approval_status": "denied"},
    )

    assert response.status_code == 200
    assert fake_profiles.updates == {"approval_status": "denied"}


def test_approval_requires_recognized_role(monkeypatch):
    monkeypatch.setattr(admin_users, "supabase", FakeProfilesQuery())
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}

    response = TestClient(app).patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"approval_status": "approved"},
    )

    assert response.status_code == 422


def test_non_admin_cannot_approve_users(monkeypatch):
    fake_profiles = FakeProfilesQuery()
    monkeypatch.setattr(admin_users, "supabase", fake_profiles)
    app.dependency_overrides[get_current_user] = lambda: {
        "app_role": "data_analyst"
    }

    response = TestClient(app).patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"approval_status": "approved", "role": "admin"},
    )

    assert response.status_code == 403
    assert fake_profiles.updates is None
