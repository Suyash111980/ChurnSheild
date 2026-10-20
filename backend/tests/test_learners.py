
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.datasets import require_processed_dataset
from app.main import app
from app.repositories import learner_repository, prediction_repository


LEARNER_ID = str(uuid4())
DATASET_ID = str(uuid4())


def allow_dataset():
    return {"id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"}


class FakeQuery:
    def __init__(self, owner, table_name):
        self.owner = owner
        self.table_name = table_name
        self.filters = []
        self.orders = []
        self.requested_range = None
        self.selected = None

    def select(self, columns, **kwargs):
        self.selected = (columns, kwargs)
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def in_(self, field, values):
        self.filters.append((field, values))
        return self

    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self

    def range(self, first, last):
        self.requested_range = (first, last)
        return self

    def limit(self, value):
        self.requested_range = (0, value - 1)
        return self

    def execute(self):
        rows = self.owner.rows.get(self.table_name, [])
        return SimpleNamespace(
            data=rows,
            count=self.owner.counts.get(self.table_name, len(rows)),
        )


class FakeSupabase:
    def __init__(self, rows=None, counts=None):
        self.rows = rows or {}
        self.counts = counts or {}
        self.queries = []

    def table(self, table_name):
        query = FakeQuery(self, table_name)
        self.queries.append(query)
        return query


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_learners_requires_authentication():
    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}"
    )
    assert response.status_code == 401


def test_malformed_bearer_token_is_unauthorized():
    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


def test_admin_can_list_paginated_learners(monkeypatch):
    fake_db = FakeSupabase(
        rows={
            "learners_latest_prediction": [
                {
                    "id": LEARNER_ID,
                    "id_student": "001",
                    "code_module": "AAA",
                    "code_presentation": "2014J",
                    "latest_risk_category": "high",
                    "dataset_id": DATASET_ID,
                }
            ]
        },
        counts={"learners_latest_prediction": 17},
    )
    monkeypatch.setattr(learner_repository, "supabase", fake_db)
    app.dependency_overrides[require_processed_dataset] = allow_dataset

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}&limit=10&offset=5"
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {
                "id": LEARNER_ID,
                "id_student": "001",
                "code_module": "AAA",
                "code_presentation": "2014J",
                "latest_risk_category": "high",
                "dataset_id": DATASET_ID,
                "student_name": None,
            }
        ],
        "limit": 10,
        "offset": 5,
        "count": 1,
        "total": 17,
        "has_more": True,
    }
    assert fake_db.queries[0].requested_range == (5, 14)
    assert fake_db.queries[0].orders == [
        ("created_at", True),
        ("id", True),
    ]


def test_learner_filters_are_database_side(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(learner_repository, "supabase", fake_db)
    app.dependency_overrides[require_processed_dataset] = allow_dataset

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}"
        "&id_student=001&code_module=AAA"
        "&code_presentation=2014J&risk_category=high"
    )

    assert response.status_code == 200
    assert fake_db.queries[0].filters == [
        ("dataset_id", DATASET_ID),
        ("external_learner_id", "001"),
        ("code_module", "AAA"),
        ("code_presentation", "2014J"),
        ("latest_risk_category", "high"),
    ]


def test_invalid_pagination_and_risk_filter_are_rejected():
    app.dependency_overrides[require_processed_dataset] = allow_dataset
    client = TestClient(app)

    for query in (
        "?limit=0",
        "?limit=101",
        "?offset=-1",
        "?risk_category=urgent",
    ):
        response = client.get(
            f"/api/v1/learners?dataset_id={DATASET_ID}{query}"
        )
        assert response.status_code == 422


def test_learner_profile_without_prediction_is_valid(monkeypatch):
    fake_db = FakeSupabase(
        rows={
            "learners_latest_prediction": [
                {
                    "id": LEARNER_ID,
                    "id_student": "001",
                    "code_module": "AAA",
                    "code_presentation": "2014J",
                    "latest_prediction_id": None,
                    "latest_model_version": None,
                    "latest_risk_probability": None,
                    "latest_risk_category": None,
                    "latest_prediction_created_at": None,
                }
            ],
            "learner_latest_feature_snapshot": [],
            "recommendations": [],
        }
    )
    monkeypatch.setattr(learner_repository, "supabase", fake_db)
    monkeypatch.setattr(prediction_repository, "supabase", fake_db)
    app.dependency_overrides[require_processed_dataset] = allow_dataset

    response = TestClient(app).get(
        f"/api/v1/learners/{LEARNER_ID}?dataset_id={DATASET_ID}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["learner"]["id"] == LEARNER_ID
    assert body["latest_prediction"] is None
    assert body["latest_feature_snapshot"] is None
    assert body["risk_explanations"] == []
    assert body["recommendations"] == []
    assert body["student_name"] is None

    # Feature snapshots must be scoped to this learner and dataset.
    feature_query = next(
        query
        for query in fake_db.queries
        if query.table_name == "learner_latest_feature_snapshot"
    )
    assert ("learner_id", LEARNER_ID) in feature_query.filters
    assert ("dataset_id", DATASET_ID) in feature_query.filters

    # Recommendations must be scoped to this learner and dataset.
    recommendation_query = next(
        query
        for query in fake_db.queries
        if query.table_name == "recommendations"
    )
    assert ("learner_id", LEARNER_ID) in recommendation_query.filters
    assert ("learners.dataset_id", DATASET_ID) in recommendation_query.filters


def test_invalid_and_missing_learner_ids(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(learner_repository, "supabase", fake_db)
    app.dependency_overrides[require_processed_dataset] = allow_dataset
    client = TestClient(app)

    assert client.get("/api/v1/learners/not-a-uuid").status_code == 422
    assert (
        client.get(
            f"/api/v1/learners/{LEARNER_ID}?dataset_id={DATASET_ID}"
        ).status_code
        == 404
    )


def test_missing_database_returns_503(monkeypatch):
    monkeypatch.setattr(learner_repository, "supabase", None)
    app.dependency_overrides[require_processed_dataset] = allow_dataset

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}"
    )
    assert response.status_code == 503


def test_database_failure_is_generic(monkeypatch):
    class BrokenDatabase:
        def table(self, _table_name):
            raise RuntimeError("private database detail")

    monkeypatch.setattr(learner_repository, "supabase", BrokenDatabase())
    app.dependency_overrides[require_processed_dataset] = allow_dataset

    response = TestClient(app).get(
        f"/api/v1/learners?dataset_id={DATASET_ID}"
    )
    assert response.status_code == 500
    assert "private database detail" not in response.text
