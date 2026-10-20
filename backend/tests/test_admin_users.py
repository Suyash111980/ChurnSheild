from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes import admin_users
from app.main import app

PENDING_ID = str(uuid4())


class FakeQuery:
    def __init__(self, client, table):
        self.client, self.table_name = client, table
        self.filters, self.selected = [], ""

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        rows = self.client.rows.get(self.table_name, [])
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self):
        self.rows = {
            "profiles": [
                {
                    "id": PENDING_ID,
                    "role": "educator",
                    "requested_role": "admin",
                    "approval_status": "pending",
                    "created_at": "2026-10-13T00:00:00Z",
                }
            ],
            "workspaces": [],
        }
        self.rpc_args = None

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, args):
        assert name == "master_review_admin_request"
        self.rpc_args = args
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(
                data={
                    "id": PENDING_ID,
                    "role": "admin",
                    "approval_status": "approved",
                    "workspace_id": str(uuid4()),
                }
            )
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_master_admin_lists_only_pending_admin_requests(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(admin_users, "supabase", fake)
    app.dependency_overrides[get_current_user] = lambda: {
        "app_role": "master_admin"
    }

    response = TestClient(app).get("/api/v1/admin/pending-users")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == PENDING_ID


def test_ordinary_admin_cannot_list_or_review_requests(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(admin_users, "supabase", fake)
    app.dependency_overrides[get_current_user] = lambda: {
        "app_role": "admin"
    }

    client = TestClient(app)

    assert client.get("/api/v1/admin/pending-users").status_code == 403
    assert (
        client.patch(
            f"/api/v1/admin/users/{PENDING_ID}/approval",
            json={"decision": "approve"},
        ).status_code
        == 403
    )
    assert fake.rpc_args is None


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_master_admin_reviews_via_atomic_database_operation(
    monkeypatch, decision
):
    fake = FakeClient()
    monkeypatch.setattr(admin_users, "supabase", fake)
    app.dependency_overrides[get_current_user] = lambda: {
        "app_role": "master_admin"
    }

    response = TestClient(app).patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"decision": decision},
    )

    assert response.status_code == 200
    assert fake.rpc_args == {
        "target_user_id": PENDING_ID,
        "decision": decision,
    }


def test_review_requires_authentication_and_expected_payload():
    client = TestClient(app)

    # A valid request without authentication must be rejected.
    response = client.patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"decision": "approve"},
    )
    assert response.status_code == 401

    # Test payload validation separately as an authenticated Master Admin.
    app.dependency_overrides[get_current_user] = lambda: {
        "app_role": "master_admin"
    }

    response = client.patch(
        f"/api/v1/admin/users/{PENDING_ID}/approval",
        json={"approval_status": "approved", "role": "admin"},
    )
    assert response.status_code == 422
