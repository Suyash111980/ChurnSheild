from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes import learners
from app.main import app


class FakeLearnerQuery:
    def __init__(self, rows):
        self.rows = rows
        self.requested_range = None

    def table(self, table_name):
        assert table_name == "learners"
        return self

    def select(self, columns):
        assert columns == "*"
        return self

    def order(self, column, desc=False):
        assert column == "created_at"
        assert desc is True
        return self

    def range(self, first, last):
        self.requested_range = (first, last)
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_learners_requires_authentication():
    response = TestClient(app).get("/api/v1/learners")
    assert response.status_code == 401


def test_malformed_bearer_token_is_unauthorized():
    response = TestClient(app).get(
        "/api/v1/learners",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "app_role", ["admin", "retention_manager", "data_analyst"]
)
def test_all_srs_roles_can_list_learners(monkeypatch, app_role):
    fake_db = FakeLearnerQuery([{"id": "learner-uuid"}])
    monkeypatch.setattr(learners, "supabase", fake_db)
    app.dependency_overrides[get_current_user] = lambda: {"app_role": app_role}

    response = TestClient(app).get("/api/v1/learners?limit=10&offset=5")

    assert response.status_code == 200
    assert response.json() == {
        "data": [{"id": "learner-uuid"}],
        "limit": 10,
        "offset": 5,
        "count": 1,
    }
    assert fake_db.requested_range == (5, 14)


def test_learners_reject_invalid_pagination():
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}
    client = TestClient(app)

    for query in ("?limit=0", "?limit=101", "?offset=-1"):
        response = client.get(f"/api/v1/learners{query}")
        assert response.status_code == 422


def test_missing_database_client_returns_safe_503(monkeypatch):
    monkeypatch.setattr(learners, "supabase", None)
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}

    response = TestClient(app).get("/api/v1/learners")

    assert response.status_code == 503
    assert "credentials" not in response.text.lower()


def test_database_error_is_generic(monkeypatch):
    class BrokenQuery:
        def table(self, _table_name):
            raise RuntimeError("internal database diagnostic")

    monkeypatch.setattr(learners, "supabase", BrokenQuery())
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}

    response = TestClient(app).get("/api/v1/learners")

    assert response.status_code == 500
    assert "internal database diagnostic" not in response.text
