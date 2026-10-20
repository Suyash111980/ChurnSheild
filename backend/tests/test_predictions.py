import csv
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.datasets import require_processed_dataset
from app.core.config import settings
from app.main import app
from app.repositories import prediction_repository
from app.services import student_display_service


PREDICTION_ID = str(uuid4())
LEARNER_ID = str(uuid4())
DATASET_ID = str(uuid4())


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = []
        self.selected = None
        self.range_value = None

    def select(self, columns, **kwargs):
        self.selected = (columns, kwargs)
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, first, last):
        self.range_value = (first, last)
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        self.database.last_query = self
        return SimpleNamespace(
            data=self.database.rows.get(self.table_name, []),
            count=self.database.counts.get(self.table_name, 0),
        )


class FakeDatabase:
    def __init__(self, rows=None, counts=None):
        self.rows = rows or {}
        self.counts = counts or {}
        self.last_query = None

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture(autouse=True)
def clear_overrides_and_display_cache():
    app.dependency_overrides.clear()
    student_display_service._load_lookup.cache_clear()
    yield
    app.dependency_overrides.clear()
    student_display_service._load_lookup.cache_clear()


def test_prediction_list_filters_and_returns_paginated_rows(monkeypatch):
    prediction = {
        "id": PREDICTION_ID,
        "learner_id": LEARNER_ID,
        "risk_probability": 0.82,
        "risk_category": "high",
        "learners": {
            "id": LEARNER_ID,
            "id_student": "01",
            "code_module": "AAA",
            "code_presentation": "2014J",
        },
    }
    db = FakeDatabase({"predictions": [prediction]}, {"predictions": 9})
    monkeypatch.setattr(prediction_repository, "supabase", db)
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }

    response = TestClient(app).get(
        f"/api/v1/predictions?dataset_id={DATASET_ID}&risk_category=high&code_module=AAA&code_presentation=2014J&limit=5&offset=2"
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["student_name"] is None
    assert response.json()["total"] == 9
    assert response.json()["has_more"] is True
    assert "learners!inner" in db.last_query.selected[0]
    assert db.last_query.filters == [
        ("risk_category", "high"),
        ("learners.code_module", "AAA"),
        ("learners.code_presentation", "2014J"),
        ("learners.dataset_id", DATASET_ID),
    ]
    assert db.last_query.range_value == (2, 6)


def test_prediction_detail_and_explanations_are_scoped_to_id(monkeypatch):
    row = {
        "id": PREDICTION_ID,
        "learner_id": LEARNER_ID,
        "risk_category": "medium",
        "learners": {"id_student": "1", "code_module": "M", "code_presentation": "P"},
    }
    explanations = [{
        "id": str(uuid4()), "prediction_id": PREDICTION_ID,
        "feature_name": "vle_total_clicks_by_cutoff", "feature_value": 7,
        "contribution": -0.2, "created_at": "2026-10-17T00:00:00Z",
    }]
    db = FakeDatabase({"predictions": [row], "risk_explanations": explanations})
    monkeypatch.setattr(prediction_repository, "supabase", db)
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }
    client = TestClient(app)

    detail = client.get(f"/api/v1/predictions/{PREDICTION_ID}?dataset_id={DATASET_ID}")
    explain = client.get(f"/api/v1/predictions/{PREDICTION_ID}/explanations?dataset_id={DATASET_ID}")

    assert detail.status_code == 200
    assert explain.status_code == 200
    assert explain.json()["data"] == explanations
    assert "predictions!inner" in db.last_query.selected[0]
    assert ("predictions.learners.dataset_id", DATASET_ID) in db.last_query.filters


def test_invalid_prediction_inputs_and_missing_record(monkeypatch):
    monkeypatch.setattr(prediction_repository, "supabase", FakeDatabase())
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }
    client = TestClient(app)

    assert client.get(f"/api/v1/predictions/not-a-uuid?dataset_id={DATASET_ID}").status_code == 422
    assert client.get(f"/api/v1/predictions?dataset_id={DATASET_ID}&risk_category=unknown").status_code == 422
    assert client.get(f"/api/v1/predictions/{PREDICTION_ID}?dataset_id={DATASET_ID}").status_code == 404


def test_prediction_name_uses_all_three_keys(monkeypatch, tmp_path):
    csv_path = tmp_path / "student_display.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id_student", "code_module", "code_presentation", "student_name"],
        )
        writer.writeheader()
        writer.writerow({"id_student": "01", "code_module": "AAA", "code_presentation": "2014J", "student_name": "Demo"})
        writer.writerow({"id_student": "01", "code_module": "BBB", "code_presentation": "2014J", "student_name": "Other"})
    monkeypatch.setattr(settings, "student_display_csv_path", str(csv_path))
    db = FakeDatabase({"predictions": [{
        "id": PREDICTION_ID,
        "learner_id": LEARNER_ID,
        "learners": {"id_student": "01", "code_module": "AAA", "code_presentation": "2014J"},
    }]})
    monkeypatch.setattr(prediction_repository, "supabase", db)
    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID, "owner_id": str(uuid4()), "status": "processed"
    }

    response = TestClient(app).get(f"/api/v1/predictions/{PREDICTION_ID}?dataset_id={DATASET_ID}")

    assert response.status_code == 200
    assert response.json()["student_name"] == "Demo"
    assert response.json()["learners"]["student_name"] == "Demo"
