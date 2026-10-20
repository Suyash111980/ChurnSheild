
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.datasets import require_processed_dataset
from app.main import app
from app.repositories import learner_repository, prediction_repository
from app.services import learner_service, student_display_service


LEARNER_ID = str(uuid4())
PREDICTION_ID = str(uuid4())
DATASET_ID = str(uuid4())


@pytest.fixture(autouse=True)
def clear_overrides_and_names():
    app.dependency_overrides.clear()
    student_display_service._load_lookup.cache_clear()
    yield
    app.dependency_overrides.clear()
    student_display_service._load_lookup.cache_clear()


class Query:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = []
        self.range_value = None

    def select(self, _columns, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, first, last):
        self.range_value = (first, last)
        return self

    def in_(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(
            data=self.database.get(self.table_name, []),
            count=len(self.database.get(self.table_name, [])),
        )


class FakeDatabase:
    def __init__(self, data):
        self.data = data

    def table(self, table_name):
        return Query(self.data, table_name)


def test_early_warning_returns_latest_records_and_no_prediction_state(
    monkeypatch,
):
    rows = [
        {
            "id": LEARNER_ID,
            "id_student": "1",
            "code_module": "AAA",
            "code_presentation": "2014J",
            "latest_prediction_id": PREDICTION_ID,
            "latest_risk_category": "high",
            "latest_risk_probability": 0.91,
        },
        {
            "id": str(uuid4()),
            "id_student": "2",
            "code_module": "BBB",
            "code_presentation": "2014B",
            "latest_prediction_id": None,
            "latest_risk_category": None,
            "latest_risk_probability": None,
        },
    ]

    database = FakeDatabase(
        {
            "learner_latest_feature_snapshot": [
                {
                    "learner_id": LEARNER_ID,
                    "features": {"clicks": 5},
                }
            ],
            "learner_latest_recommendation": [
                {
                    "learner_id": LEARNER_ID,
                    "status": "pending",
                }
            ],
        }
    )

    monkeypatch.setattr(learner_repository, "supabase", database)
    monkeypatch.setattr(prediction_repository, "supabase", database)
    monkeypatch.setattr(
        learner_repository,
        "list_early_warning",
        lambda **_filters: SimpleNamespace(data=rows, count=2),
    )

    monkeypatch.setattr(
        prediction_repository,
        "list_explanations_for_predictions",
        lambda _ids, _dataset_id: [
            {
                "prediction_id": PREDICTION_ID,
                "feature_name": "clicks",
                "contribution": -0.3,
            }
        ],
    )

    monkeypatch.setattr(
        student_display_service,
        "get_student_name",
        lambda _row: None,
    )

    result = learner_service.get_early_warning_page(
        dataset_id=DATASET_ID,
        limit=20,
        offset=0,
    )

    assert result["data"][0]["latest_risk_category"] == "high"
    assert (
        result["data"][0]["latest_feature_snapshot"]["features"]
        == {"clicks": 5}
    )
    assert result["data"][0]["latest_explanations"][0]["contribution"] == -0.3
    assert result["data"][0]["latest_recommendation"]["status"] == "pending"
    assert result["data"][1]["prediction_state"] == "unavailable"
    assert result["data"][1]["latest_risk_category"] is None


def test_early_warning_endpoint_requires_auth_and_validates_filters(
    monkeypatch,
):
    monkeypatch.setattr(
        learner_repository,
        "supabase",
        FakeDatabase({}),
    )

    client = TestClient(app)

    assert (
        client.get(
            f"/api/v1/early-warning?dataset_id={DATASET_ID}"
        ).status_code
        == 401
    )

    app.dependency_overrides[require_processed_dataset] = lambda: {
        "id": DATASET_ID,
        "owner_id": str(uuid4()),
        "status": "processed",
    }

    assert (
        client.get(
            f"/api/v1/early-warning?dataset_id={DATASET_ID}"
            "&risk_category=critical"
        ).status_code
        == 422
    )


def test_early_warning_passes_dataset_id_to_enrichment_queries(monkeypatch):
    learner_id = str(uuid4())
    prediction_id = str(uuid4())
    requested_dataset_id = str(uuid4())

    rows = [
        {
            "id": learner_id,
            "latest_prediction_id": prediction_id,
            "latest_risk_category": "high",
            "latest_risk_probability": 0.91,
        }
    ]

    observed = {}

    monkeypatch.setattr(
        learner_repository,
        "list_early_warning",
        lambda **filters: (
            observed.update(list_filters=filters)
            or SimpleNamespace(data=rows, count=1)
        ),
    )

    def fake_features(learner_ids, dataset_id):
        observed["feature_learner_ids"] = learner_ids
        observed["feature_dataset_id"] = dataset_id

        return [
            {
                "learner_id": learner_id,
                "features": {"clicks": 5},
            }
        ]

    def fake_recommendations(learner_ids, dataset_id):
        observed["recommendation_learner_ids"] = learner_ids
        observed["recommendation_dataset_id"] = dataset_id

        return [
            {
                "learner_id": learner_id,
                "status": "pending",
            }
        ]

    def fake_explanations(prediction_ids, dataset_id):
        observed["prediction_ids"] = prediction_ids
        observed["explanation_dataset_id"] = dataset_id

        return [
            {
                "prediction_id": prediction_id,
                "feature_name": "clicks",
            }
        ]

    monkeypatch.setattr(
        learner_repository,
        "get_latest_feature_snapshots",
        fake_features,
    )
    monkeypatch.setattr(
        learner_repository,
        "get_latest_recommendations",
        fake_recommendations,
    )
    monkeypatch.setattr(
        prediction_repository,
        "list_explanations_for_predictions",
        fake_explanations,
    )
    monkeypatch.setattr(
        student_display_service,
        "get_student_name",
        lambda _row: None,
    )

    result = learner_service.get_early_warning_page(
        dataset_id=requested_dataset_id,
        limit=20,
        offset=0,
    )

    assert observed["list_filters"]["dataset_id"] == requested_dataset_id

    assert observed["feature_learner_ids"] == [learner_id]
    assert observed["feature_dataset_id"] == requested_dataset_id

    assert observed["recommendation_learner_ids"] == [learner_id]
    assert observed["recommendation_dataset_id"] == requested_dataset_id

    assert observed["prediction_ids"] == [prediction_id]
    assert observed["explanation_dataset_id"] == requested_dataset_id

    assert (
        result["data"][0]["latest_feature_snapshot"]["features"]
        == {"clicks": 5}
    )
    assert result["data"][0]["latest_recommendation"]["status"] == "pending"
