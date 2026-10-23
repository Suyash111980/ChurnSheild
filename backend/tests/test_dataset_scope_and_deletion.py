from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.routes.datasets import delete_dataset
from app.api.routes.early_warning import early_warning
from app.api.routes.learners import get_learners
from app.repositories import dataset_repository, learner_repository
from app.services import learner_service
from app.api.routes import early_warning as early_warning_module

OWNER = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DATASET_A = str(uuid4())
DATASET_B = str(uuid4())
USER = {"id": OWNER, "app_role": "admin", "workspace_id": WORKSPACE}


def _page():
    return {"data": [], "limit": 20, "offset": 0, "count": 0, "total": 0, "has_more": False}


def test_learners_all_scope_uses_explicit_contract_and_only_authorized_processed_datasets(monkeypatch):
    captured = {}
    monkeypatch.setattr(dataset_repository, "supabase", object())
    monkeypatch.setattr(learner_repository, "supabase", object())
    monkeypatch.setattr(dataset_repository, "list_all_owned_datasets", lambda **_kwargs: [
        {"id": DATASET_A, "status": "processed"}, {"id": DATASET_B, "status": "failed"},
    ])
    monkeypatch.setattr(learner_service, "list_learners", lambda **kwargs: captured.update(kwargs) or _page())
    result = get_learners(dataset_id=None, scope="all", limit=20, offset=0, id_student=None,
                         code_module=None, code_presentation=None, risk_category=None,
                         q=None, sort=None, direction="asc", user=USER)
    assert result["total"] == 0
    assert captured["dataset_id"] is None
    assert captured["dataset_ids"] == [DATASET_A]


def test_learners_accept_individual_uuid_and_reject_missing_scope(monkeypatch):
    monkeypatch.setattr(dataset_repository, "supabase", object())
    monkeypatch.setattr(learner_repository, "supabase", object())
    monkeypatch.setattr(dataset_repository, "get_owned_dataset", lambda dataset_id, *_args: {"id": dataset_id, "status": "processed"})
    monkeypatch.setattr(learner_service, "list_learners", lambda **_kwargs: _page())
    assert get_learners(dataset_id=DATASET_A, scope=None, limit=20, offset=0, id_student=None,
                        code_module=None, code_presentation=None, risk_category=None,
                        q=None, sort=None, direction="asc", user=USER)["total"] == 0
    with pytest.raises(HTTPException) as missing:
        get_learners(dataset_id=None, scope=None, limit=20, offset=0, id_student=None,
                     code_module=None, code_presentation=None, risk_category=None,
                     q=None, sort=None, direction="asc", user=USER)
    assert missing.value.status_code == 422


def test_early_warning_all_scope_uses_workspace_dataset_ids_and_search(monkeypatch):
    captured = {}
    monkeypatch.setattr(dataset_repository, "supabase", object())
    monkeypatch.setattr(learner_repository, "supabase", object())
    monkeypatch.setattr(dataset_repository, "list_all_owned_datasets", lambda **_kwargs: [
        {"id": DATASET_A, "status": "processed"}, {"id": DATASET_B, "status": "processed"},
    ])
    monkeypatch.setattr(early_warning_module, "get_early_warning_page", lambda **kwargs: captured.update(kwargs) or _page())
    result = early_warning(dataset_id=None, scope="all", limit=20, offset=0, risk_category=None,
                           code_module=None, code_presentation=None, q="001", user=USER)
    assert result["total"] == 0
    assert captured["dataset_id"] is None
    assert captured["dataset_ids"] == [DATASET_A, DATASET_B]
    assert captured["search"] == "001"


def test_list_route_openapi_keeps_dataset_id_uuid_typed_and_scope_explicit():
    schema = __import__("app.main", fromlist=["app"]).app.openapi()
    for path in ("/api/v1/learners", "/api/v1/early-warning"):
        parameters = {param["name"]: param for param in schema["paths"][path]["get"]["parameters"]}
        assert {variant.get("format") for variant in parameters["dataset_id"]["schema"]["anyOf"]} >= {"uuid"}
        assert any(variant.get("const") == "all" for variant in parameters["scope"]["schema"]["anyOf"])


def test_dataset_delete_uses_owner_workspace_and_request_jwt_and_hides_other_workspace(monkeypatch):
    rows = {
        DATASET_A: {"owner_id": OWNER, "workspace_id": WORKSPACE, "status": "processed", "learners": 2, "predictions": 2, "explanations": 1, "recommendations": 1},
        DATASET_B: {"owner_id": "22222222-2222-4222-8222-222222222222", "workspace_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "status": "processed", "learners": 1},
    }
    calls = []

    def delete(dataset_id, owner_id, workspace_id, access_token):
        calls.append((dataset_id, owner_id, workspace_id, access_token))
        row = rows.get(dataset_id)
        if not row or row["owner_id"] != owner_id or row["workspace_id"] != workspace_id or row["status"] == "processing":
            return None
        del rows[dataset_id]  # fake one transactional database delete with FK cascades
        return {"id": dataset_id}

    monkeypatch.setattr(dataset_repository, "supabase", object())
    monkeypatch.setattr(dataset_repository, "delete_owned_dataset", delete)
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="synthetic-jwt")
    response = delete_dataset(dataset_id=DATASET_A, user=USER, credentials=token)
    assert response.status_code == 204
    assert DATASET_A not in rows
    with pytest.raises(HTTPException) as forged:
        delete_dataset(dataset_id=DATASET_B, user=USER, credentials=token)
    assert forged.value.status_code == 404
    assert DATASET_B in rows
    assert calls[0] == (DATASET_A, OWNER, WORKSPACE, "synthetic-jwt")


def test_delete_policy_migration_is_workspace_scoped_and_cascade_is_existing_schema():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    delete_policy = (root / "database" / "migrations" / "008_dataset_delete_policy.sql").read_text().lower()
    initial = (root / "database" / "migrations" / "001_initial_schema.sql").read_text().lower()
    ownership = (root / "database" / "migrations" / "005_dataset_ownership.sql").read_text().lower()
    assert "for delete to authenticated using" in delete_policy
    assert "owner_id = (select auth.uid())" in delete_policy
    assert "w.status = 'active'" in delete_policy
    assert "p.approval_status = 'approved'" in delete_policy
    assert "status <> 'processing'" in delete_policy
    assert "learner_id uuid not null references public.learners(id) on delete cascade" in initial
    assert "prediction_id uuid not null references public.predictions(id) on delete cascade" in initial
    assert "references public.dataset_uploads(id) on delete cascade" in ownership


def test_delete_repository_uses_publishable_client_and_authenticated_user_jwt(monkeypatch):
    import supabase as supabase_module

    from app.core.config import settings

    state = {"auth": None, "key": None, "filters": []}

    class Query:
        def delete(self): return self
        def eq(self, field, value): state["filters"].append((field, value)); return self
        def neq(self, field, value): state["filters"].append((field, value)); return self
        def select(self, fields): state["select"] = fields; return self
        def execute(self): return type("Response", (), {"data": [{"id": DATASET_A}]})()

    class Postgrest:
        def auth(self, token): state["auth"] = token

    class Client:
        postgrest = Postgrest()
        def table(self, name): state["table"] = name; return Query()

    def factory(url, key):
        state["url"] = url
        state["key"] = key
        return Client()

    monkeypatch.setattr(settings, "supabase_url", "https://project.example")
    monkeypatch.setattr(settings, "supabase_publishable_key", "publishable-test-key")
    monkeypatch.setattr(supabase_module, "create_client", factory)
    result = dataset_repository.delete_owned_dataset(DATASET_A, OWNER, WORKSPACE, "real-user-jwt")
    assert result == {"id": DATASET_A}
    assert state["key"] == "publishable-test-key"
    assert state["auth"] == "real-user-jwt"
    assert state["table"] == "dataset_uploads"
    assert ("id", DATASET_A) in state["filters"]
    assert ("owner_id", OWNER) in state["filters"]
    assert ("workspace_id", WORKSPACE) in state["filters"]
    assert ("status", "processing") in state["filters"]
