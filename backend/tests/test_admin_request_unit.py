from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_roles
from app.main import app
from app.api.routes import admin_users
from app.schemas.admin_request import AdminRequestPage, ReviewDecision


MASTER_ID = str(uuid4())
TARGET_ID = str(uuid4())


class FakeRpcClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def rpc(self, name, args):
        self.calls.append((name, args))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.response))


def test_master_admin_request_page_validates_counts_and_name_projection(monkeypatch):
    fake = FakeRpcClient({
        "data": [{
            "id": TARGET_ID,
            "display_name": "Applicant Name",
            "email": "applicant@example.test",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }],
        "counts": {"pending": 1, "approved": 2, "rejected": 0},
        "count": 1,
        "total": 3,
        "limit": 20,
        "offset": 0,
        "has_more": False,
        "activity": [],
    })
    monkeypatch.setattr(admin_users, "supabase", fake)

    result = admin_users.list_admin_requests(
        status="pending",
        search=None,
        date_from=None,
        date_to=None,
        sort="newest",
        limit=20,
        offset=0,
        _master={"id": MASTER_ID},
    )

    assert isinstance(result, AdminRequestPage)
    assert result.data[0].display_name == "Applicant Name"
    assert result.counts.approved == 2
    assert fake.calls[0][0] == "master_list_admin_requests"
    assert fake.calls[0][1]["status_filter"] == "pending"


@pytest.mark.parametrize("status", ["pending", "approved", "rejected"])
def test_list_route_passes_status_sort_and_pagination_to_database(status, monkeypatch):
    fake = FakeRpcClient({
        "data": [],
        "counts": {"pending": 0, "approved": 0, "rejected": 0},
        "count": 0,
        "total": 0,
        "limit": 10,
        "offset": 20,
        "has_more": False,
        "activity": [],
    })
    monkeypatch.setattr(admin_users, "supabase", fake)

    result = admin_users.list_admin_requests(
        status=status,
        search="Taylor",
        date_from=None,
        date_to=None,
        sort="reviewed",
        limit=10,
        offset=20,
        _master={"id": MASTER_ID},
    )

    assert result.count == 0
    assert fake.calls[0][1] == {
        "status_filter": status,
        "search_query": "Taylor",
        "date_from": None,
        "date_to": None,
        "sort_by": "reviewed",
        "page_limit": 10,
        "page_offset": 20,
    }


def test_admin_request_route_is_included_once_and_documented():
    schema = app.openapi()
    operations = schema["paths"]["/api/v1/admin/requests"]
    assert set(operations) == {"get"}
    params = {param["name"]: param for param in operations["get"]["parameters"]}
    assert params["status"]["schema"]["pattern"] == "^(pending|approved|rejected)$"
    assert params["limit"]["schema"]["maximum"] == 100
    assert params["offset"]["schema"]["minimum"] == 0
    assert "/api/v1/admin/users/{user_id}/approval" in schema["paths"]
    assert "/api/v1/admin/requests/{user_id}/details" in schema["paths"]


def test_request_details_are_scoped_to_selected_admin(monkeypatch):
    workspace_id = str(uuid4())

    class Query:
        def __init__(self, table):
            self.table = table
            self.filters = []

        def select(self, _columns): return self
        def eq(self, column, value):
            self.filters.append((column, value))
            return self
        def limit(self, _value): return self
        def order(self, *_args, **_kwargs): return self
        def execute(self):
            if self.table == "profiles":
                return SimpleNamespace(data=[{"id": TARGET_ID}] if ("id", TARGET_ID) in self.filters and ("requested_role", "admin") in self.filters else [])
            if self.table == "workspaces":
                assert ("admin_user_id", TARGET_ID) in self.filters
                return SimpleNamespace(data=[{"id": workspace_id, "created_at": "2026-10-01T10:00:00Z"}])
            assert self.table == "dataset_uploads"
            assert ("owner_id", TARGET_ID) in self.filters
            return SimpleNamespace(data=[{"filename": "owned.csv", "uploaded_at": "2026-10-02T10:00:00Z", "row_count": 4}])

    class Client:
        def table(self, name): return Query(name)

    monkeypatch.setattr(admin_users, "supabase", Client())
    result = admin_users.get_admin_request_details(UUID(TARGET_ID), _master={"id": MASTER_ID})

    assert result.workspaces[0].workspace_id == workspace_id
    assert result.workspaces[0].workspace_name is None
    assert result.datasets[0].filename == "owned.csv"
    assert result.datasets[0].row_count == 4


def test_request_details_returns_empty_lists_when_admin_has_no_records(monkeypatch):
    class Query:
        def __init__(self, table): self.table = table
        def select(self, _columns): return self
        def eq(self, *_args): return self
        def limit(self, _value): return self
        def order(self, *_args, **_kwargs): return self
        def execute(self):
            return SimpleNamespace(data=[{"id": TARGET_ID}] if self.table == "profiles" else [])

    class Client:
        def table(self, name): return Query(name)

    monkeypatch.setattr(admin_users, "supabase", Client())
    result = admin_users.get_admin_request_details(UUID(TARGET_ID), _master={"id": MASTER_ID})
    assert result.workspaces == []
    assert result.datasets == []


def test_master_admin_review_rpc_receives_trusted_reviewer_and_reason(monkeypatch):
    fake = FakeRpcClient({
        "id": TARGET_ID,
        "role": "admin",
        "approval_status": "approved",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": MASTER_ID,
        "workspace_id": str(uuid4()),
    })
    monkeypatch.setattr(admin_users, "supabase", fake)

    result = admin_users.review_admin_request(
        user_id=UUID(TARGET_ID),
        decision=ReviewDecision(decision="approve"),
        _master={"id": MASTER_ID, "app_role": "master_admin"},
    )

    assert result["data"]["approval_status"] == "approved"
    assert fake.calls == [(
        "master_review_admin_request",
        {
            "target_user_id": TARGET_ID,
            "decision": "approve",
            "reviewer_user_id": MASTER_ID,
            "review_reason": None,
        },
    )]


def test_non_master_role_is_rejected_by_backend_dependency():
    dependency = require_roles("master_admin")
    with pytest.raises(HTTPException) as error:
        dependency({"id": str(uuid4()), "app_role": "admin"})
    assert error.value.status_code == 403


def test_malformed_rpc_payload_fails_closed(monkeypatch):
    monkeypatch.setattr(admin_users, "supabase", FakeRpcClient(None))
    with pytest.raises(HTTPException) as error:
        admin_users.list_admin_requests(
            status="pending",
            search=None,
            date_from=None,
            date_to=None,
            sort="newest",
            limit=20,
            offset=0,
            _master={"id": MASTER_ID},
        )
    assert error.value.status_code == 503


def test_database_failure_returns_safe_503(monkeypatch):
    class FailingClient:
        def rpc(self, _name, _args):
            raise RuntimeError("private provider details")

    monkeypatch.setattr(admin_users, "supabase", FailingClient())
    with pytest.raises(HTTPException) as error:
        admin_users.list_admin_requests(
            status="pending", search=None, date_from=None, date_to=None,
            sort="newest", limit=20, offset=0, _master={"id": MASTER_ID},
        )
    assert error.value.status_code == 503
    assert "private provider details" not in error.value.detail


def test_reversed_request_dates_are_rejected_before_database_call(monkeypatch):
    fake = FakeRpcClient(None)
    monkeypatch.setattr(admin_users, "supabase", fake)
    with pytest.raises(HTTPException) as error:
        admin_users.list_admin_requests(
            status="pending", search=None,
            date_from=date(2026, 10, 20),
            date_to=date(2026, 10, 1),
            sort="newest", limit=20, offset=0, _master={"id": MASTER_ID},
        )
    assert error.value.status_code == 422
    assert not fake.calls
