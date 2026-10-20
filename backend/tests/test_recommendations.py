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
    fake = FakeRecommendationQuery([{"id": RECOMMENDATION_ID, "status": "pending"}])
    monkeypatch.setattr(recommendation_repository, "supabase", fake)
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }

    response = TestClient(app).get(
        f"/api/v1/recommendations?dataset_id={DATASET_ID}&learner_id={uuid4()}&status=pending&limit=10&offset=5"
    )

    assert response.status_code == 200
    assert "learners!inner" in fake.selected
    assert response.json()["count"] == 1
    assert fake.filters[0] == ("learners.dataset_id", DATASET_ID)
    assert fake.filters[1][0] == "learner_id"
    assert fake.filters[2] == ("status", "pending")
    assert fake.requested_range == (5, 14)


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
