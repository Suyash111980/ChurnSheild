from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.datasets import require_processed_dataset
from app.main import app
from app.repositories import recommendation_repository
from app.services import recommendation_service


RECOMMENDATION_ID = str(uuid4())
DATASET_ID = str(uuid4())


class FakeRecommendationQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.selected = None
        self.updates = None
        self.requested_range = None

    def table(self, table_name):
        assert table_name == "recommendations"
        return self

    def select(self, columns, **_kwargs):
        self.selected = columns
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, first, last):
        self.requested_range = (first, last)
        return self

    def limit(self, _value):
        return self

    def update(self, values):
        self.updates = values
        return self

    def execute(self):
        if self.updates is not None:
            row = self.rows[0] if self.rows else None
            if row and any(row.get(field) != value for field, value in self.filters if field in row):
                row = None
            row = {**row, **self.updates} if row else None
            return SimpleNamespace(data=[row] if row else [])
        return SimpleNamespace(data=self.rows, count=len(self.rows))


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_recommendations_are_paginated_and_filterable(monkeypatch):
    learner_id = str(uuid4())
    prediction_id = str(uuid4())
    fake = FakeRecommendationQuery([{
        "id": RECOMMENDATION_ID, "status": "pending", "learner_id": learner_id,
        "prediction_id": prediction_id, "rule_id": "check_in", "action": "Offer a check-in", "reason": "Saved evidence.",
        "learners": {
            "dataset_id": DATASET_ID, "external_learner_id": "00123",
            "code_module": "AAA", "code_presentation": "2014J",
        },
        "prediction": {"risk_category": "high", "risk_probability": 0.82, "model_version": "model-v1"},
    }])
    monkeypatch.setattr(recommendation_repository, "supabase", fake)
    monkeypatch.setattr(
        recommendation_repository,
        "count_recommendations_by_status",
        lambda **_filters: {"pending": 8, "in_progress": 2, "completed": 1, "dismissed": 0},
    )
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }

    response = TestClient(app).get(
        f"/api/v1/recommendations?dataset_id={DATASET_ID}&learner_id={learner_id}&prediction_id={prediction_id}&status=pending&risk_level=high&limit=10&offset=5"
    )

    assert response.status_code == 200
    assert "learners!inner" in fake.selected
    assert "prediction:predictions" in fake.selected
    assert "predictions!inner" in fake.selected
    assert response.json()["count"] == 1
    assert response.json()["status_counts"] == {
        "pending": 8, "in_progress": 2, "completed": 1, "dismissed": 0,
    }
    assert response.json()["data"][0]["external_learner_id"] == "00123"
    assert response.json()["data"][0]["code_module"] == "AAA"
    assert "learners" not in response.json()["data"][0]
    assert fake.filters[0] == ("learners.dataset_id", DATASET_ID)
    assert fake.filters[1][0] == "learner_id"
    assert fake.filters[2] == ("prediction_id", prediction_id)
    assert fake.filters[3] == ("status", "pending")
    assert fake.filters[4] == ("prediction.risk_category", "high")
    assert fake.requested_range == (5, 14)
    assert response.json()["status_counts"] == {
        "pending": 8, "in_progress": 2, "completed": 1, "dismissed": 0,
    }
    assert response.json()["data"][0]["learner"]["external_learner_id"] == "00123"
    assert response.json()["data"][0]["prediction"]["risk_probability"] == 0.82


def test_recommendation_risk_filter_rejects_unknown_values():
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }
    response = TestClient(app).get(
        f"/api/v1/recommendations?dataset_id={DATASET_ID}&risk_level=critical"
    )
    assert response.status_code == 422


def test_status_totals_are_dataset_scoped_head_counts(monkeypatch):
    expected = {"pending": 4, "in_progress": 3, "completed": 2, "dismissed": 1}
    queries = []

    class CountQuery:
        def __init__(self):
            self.filters = []
            self.columns = None
            self.options = None

        def table(self, name):
            assert name == "recommendations"
            self.filters = []
            queries.append(self)
            return self

        def select(self, columns, **options):
            self.columns = columns
            self.options = options
            return self

        def eq(self, field, value):
            self.filters.append((field, value))
            return self

        def execute(self):
            selected_status = next(value for field, value in self.filters if field == "status")
            return SimpleNamespace(count=expected[selected_status], data=None)

    monkeypatch.setattr(recommendation_repository, "supabase", CountQuery())
    counts = recommendation_repository.count_recommendations_by_status(
        dataset_id=DATASET_ID, learner_id="learner-1"
    )

    assert counts == expected
    assert len(queries) == 4
    for query in queries:
        assert query.options == {"count": "exact", "head": True}
        assert ("learners.dataset_id", DATASET_ID) in query.filters
        assert ("learner_id", "learner-1") in query.filters


def test_status_count_query_is_dataset_scoped_and_ignores_pagination_and_status_filter(monkeypatch):
    class StatusCountQuery:
        def __init__(self, rows):
            self.rows = rows
            self.filters = []
            self.requests = []

        def table(self, _name):
            return self

        def select(self, _columns, **kwargs):
            self.requests.append(kwargs)
            return self

        def eq(self, field, value):
            self.filters.append((field, value))
            return self

        def execute(self):
            self.requests[-1]["filters"] = list(self.filters)
            matched = [row for row in self.rows if all(
                row.get("learner_dataset_id") == value if field == "learners.dataset_id"
                else row.get(field) == value
                for field, value in self.filters
            )]
            self.filters = []
            return SimpleNamespace(data=[], count=len(matched))

    fake = StatusCountQuery([
        {"learner_dataset_id": DATASET_ID, "learner_id": "learner-1", "prediction_id": "prediction-1", "status": "pending"},
        {"learner_dataset_id": DATASET_ID, "learner_id": "learner-1", "prediction_id": "prediction-2", "status": "pending"},
        {"learner_dataset_id": DATASET_ID, "learner_id": "learner-1", "prediction_id": "prediction-3", "status": "completed"},
        {"learner_dataset_id": str(uuid4()), "learner_id": "learner-1", "prediction_id": "prediction-1", "status": "dismissed"},
    ])
    monkeypatch.setattr(recommendation_repository, "supabase", fake)

    counts = recommendation_repository.count_recommendations_by_status(
        dataset_id=DATASET_ID, learner_id="learner-1"
    )

    assert counts == {"pending": 2, "in_progress": 0, "completed": 1, "dismissed": 0}
    assert len(fake.requests) == 4
    assert all(request["count"] == "exact" and request["head"] is True for request in fake.requests)
    assert all(("learners.dataset_id", DATASET_ID) in request["filters"] for request in fake.requests)
    assert all(("learner_id", "learner-1") in request["filters"] for request in fake.requests)


def test_recommendation_page_includes_unpaginated_status_totals(monkeypatch):
    monkeypatch.setattr(
        recommendation_repository,
        "list_recommendations",
        lambda **_filters: SimpleNamespace(data=[], count=0),
    )
    monkeypatch.setattr(
        recommendation_repository,
        "count_recommendations_by_status",
        lambda **filters: {
            "pending": 15, "in_progress": 4, "completed": 5, "dismissed": 1,
        } if filters["dataset_id"] == DATASET_ID else pytest.fail("dataset scope was lost"),
    )

    result = recommendation_service.list_recommendations(
        dataset_id=DATASET_ID, limit=20, offset=0, recommendation_status="dismissed",
    )

    assert result["data"] == []
    assert result["total"] == 0
    assert result["has_more"] is False
    assert result["status_counts"] == {
        "pending": 15, "in_progress": 4, "completed": 5, "dismissed": 1,
    }


def test_recommendation_update_access_is_role_restricted(monkeypatch):
    monkeypatch.setattr(recommendation_repository, "supabase", FakeRecommendationQuery([]))
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "master_admin"}

    response = TestClient(app).patch(
        f"/api/v1/recommendations/{RECOMMENDATION_ID}?dataset_id={DATASET_ID}",
        json={"status": "in_progress"},
    )

    assert response.status_code == 403


def test_recommendation_update_validates_transition_and_sets_timestamp(monkeypatch):
    current = {"id": RECOMMENDATION_ID, "learner_id": "learner-1", "status": "pending"}
    monkeypatch.setattr(recommendation_repository, "get_recommendation", lambda _id, _dataset_id: current)
    updates = {}

    def fake_update(_id, learner_id, from_status, to_status, updated_at):
        updates.update(learner_id=learner_id, from_status=from_status, status=to_status, updated_at=updated_at)
        return {**current, "status": to_status, "updated_at": updated_at}

    monkeypatch.setattr(recommendation_repository, "set_recommendation_status", fake_update)
    result = recommendation_service.update_status(RECOMMENDATION_ID, DATASET_ID, "in_progress")

    assert result["status"] == "in_progress"
    assert updates["from_status"] == "pending"
    assert updates["learner_id"] == "learner-1"
    assert updates["updated_at"]


def test_recommendation_mutation_repeats_verified_learner_scope(monkeypatch):
    current = {"id": RECOMMENDATION_ID, "learner_id": "verified-learner", "status": "pending"}
    monkeypatch.setattr(recommendation_repository, "get_recommendation", lambda _id, _dataset_id: current)
    captured = {}

    def fake_update(recommendation_id, learner_id, from_status, to_status, updated_at):
        captured.update(recommendation_id=recommendation_id, learner_id=learner_id)
        return {**current, "status": to_status, "updated_at": updated_at}

    monkeypatch.setattr(recommendation_repository, "set_recommendation_status", fake_update)
    recommendation_service.update_status(RECOMMENDATION_ID, DATASET_ID, "in_progress")
    assert captured == {"recommendation_id": RECOMMENDATION_ID, "learner_id": "verified-learner"}


def test_repository_update_is_conditioned_on_learner_and_status(monkeypatch):
    fake = FakeRecommendationQuery([{
        "id": RECOMMENDATION_ID, "learner_id": "verified-learner", "status": "pending"
    }])
    monkeypatch.setattr(recommendation_repository, "supabase", fake)

    result = recommendation_repository.set_recommendation_status(
        RECOMMENDATION_ID, "verified-learner", "pending", "in_progress", "2026-10-17T00:00:00+00:00"
    )

    assert result["status"] == "in_progress"
    assert ("id", RECOMMENDATION_ID) in fake.filters
    assert ("learner_id", "verified-learner") in fake.filters
    assert ("status", "pending") in fake.filters

    mismatch = recommendation_repository.set_recommendation_status(
        RECOMMENDATION_ID, "another-learner", "pending", "dismissed", "2026-10-17T00:00:00+00:00"
    )
    assert mismatch is None


def test_dataset_scoped_lookup_is_carried_into_recommendation_mutation(monkeypatch):
    row = {
        "id": RECOMMENDATION_ID,
        "learner_id": "verified-learner",
        "dataset_id": DATASET_ID,
        "status": "pending",
    }

    class DatasetScopedQuery(FakeRecommendationQuery):
        def table(self, table_name):
            self.filters = []
            self.updates = None
            return super().table(table_name)

        def execute(self):
            executed_filters.append(list(self.filters))
            matched = self.rows[0] if self.rows else None
            for field, value in self.filters:
                actual_field = "dataset_id" if field == "learners.dataset_id" else field
                if matched and actual_field in matched and matched[actual_field] != value:
                    matched = None
            if self.updates is not None:
                matched = {**matched, **self.updates} if matched else None
                return SimpleNamespace(data=[matched] if matched else [])
            return SimpleNamespace(data=[matched] if matched else [], count=int(matched is not None))

    fake = DatasetScopedQuery([row])
    executed_filters = []
    monkeypatch.setattr(recommendation_repository, "supabase", fake)

    other_dataset_id = str(uuid4())
    assert recommendation_repository.get_recommendation(RECOMMENDATION_ID, other_dataset_id) is None
    assert fake.filters[-1] == ("learners.dataset_id", other_dataset_id)

    result = recommendation_service.update_status(RECOMMENDATION_ID, DATASET_ID, "in_progress")
    assert result["status"] == "in_progress"
    assert any(("learners.dataset_id", DATASET_ID) in filters for filters in executed_filters)
    assert ("learner_id", "verified-learner") in executed_filters[-1]


@pytest.mark.parametrize("terminal_status", ["completed", "dismissed"])
def test_terminal_recommendation_status_cannot_be_reopened(monkeypatch, terminal_status):
    monkeypatch.setattr(
        recommendation_repository,
        "get_recommendation",
        lambda _id, _dataset_id: {"id": RECOMMENDATION_ID, "status": terminal_status},
    )
    with pytest.raises(ValueError, match="invalid_transition"):
        recommendation_service.update_status(RECOMMENDATION_ID, DATASET_ID, "in_progress")


def test_same_recommendation_status_is_idempotent(monkeypatch):
    current = {"id": RECOMMENDATION_ID, "status": "completed"}
    monkeypatch.setattr(recommendation_repository, "get_recommendation", lambda _id, _dataset_id: current)
    monkeypatch.setattr(
        recommendation_repository,
        "set_recommendation_status",
        lambda *_args: pytest.fail("idempotent update must not write"),
    )

    assert recommendation_service.update_status(RECOMMENDATION_ID, DATASET_ID, "completed") == current
