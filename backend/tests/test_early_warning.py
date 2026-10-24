
from types import SimpleNamespace
from uuid import uuid4

import pytest

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
        lambda _ids, _dataset_id, _dataset_ids=None: [
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


def test_early_warning_exposes_uuid_scope_and_risk_filter_contract():
    parameters = {
        item["name"]: item
        for item in app.openapi()["paths"]["/api/v1/early-warning"]["get"]["parameters"]
    }
    assert any(value.get("format") == "uuid" for value in parameters["dataset_id"]["schema"]["anyOf"])
    assert any(value.get("const") == "all" for value in parameters["scope"]["schema"]["anyOf"])
    assert parameters["limit"]["schema"]["maximum"] == 100
    risk_schema = parameters["risk_category"]["schema"]
    assert any(
        value.get("pattern") == "^(low|medium|high)$"
        for value in risk_schema.get("anyOf", [risk_schema])
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

    def fake_features(learner_ids, dataset_id, dataset_ids=None):
        observed["feature_learner_ids"] = learner_ids
        observed["feature_dataset_id"] = dataset_id
        observed["feature_dataset_ids"] = dataset_ids

        return [
            {
                "learner_id": learner_id,
                "features": {"clicks": 5},
            }
        ]

    def fake_recommendations(learner_ids, dataset_id, dataset_ids=None):
        observed["recommendation_learner_ids"] = learner_ids
        observed["recommendation_dataset_id"] = dataset_id
        observed["recommendation_dataset_ids"] = dataset_ids

        return [
            {
                "learner_id": learner_id,
                "status": "pending",
            }
        ]

    def fake_explanations(prediction_ids, dataset_id, dataset_ids=None):
        observed["prediction_ids"] = prediction_ids
        observed["explanation_dataset_id"] = dataset_id
        observed["explanation_dataset_ids"] = dataset_ids

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

def test_early_warning_pagination_reaches_all_750_dataset_records_without_duplicates(monkeypatch):
    rows = []
    categories = ("high", "medium", "low")
    for index in range(750):
        has_prediction = index % 5 != 0
        rows.append({
            "id": f"learner-{index}",
            "dataset_id": DATASET_ID,
            "external_learner_id": str(index),
            "code_module": "AAA",
            "code_presentation": "2014J",
            "latest_prediction_id": f"prediction-{index}" if has_prediction else None,
            "latest_risk_category": categories[index % 3] if has_prediction else None,
            "latest_risk_probability": 0.9 - (index % 90) / 100 if has_prediction else None,
        })

    class Query:
        def __init__(self, table_name):
            self.table_name = table_name
            self.filters = []
            self.window = (0, 749)

        def select(self, *_args, **_kwargs): return self
        def eq(self, key, value): self.filters.append((key, value)); return self
        def in_(self, key, values): self.filters.append((key, set(values))); return self
        def order(self, *_args, **_kwargs): return self
        def limit(self, *_args): return self
        def range(self, start, end): self.window = (start, end); return self

        def execute(self):
            source = rows if self.table_name == "learners_latest_prediction" else []
            selected = list(source)
            for key, value in self.filters:
                if isinstance(value, set):
                    selected = [row for row in selected if row.get(key) in value]
                else:
                    selected = [row for row in selected if row.get(key) == value]
            start, end = self.window
            return SimpleNamespace(data=selected[start:end + 1], count=len(selected))

    class Database:
        def table(self, table_name): return Query(table_name)

    database = Database()
    monkeypatch.setattr(learner_repository, "supabase", database)
    monkeypatch.setattr(prediction_repository, "supabase", database)
    monkeypatch.setattr(student_display_service, "get_student_name", lambda _row: None)

    visited = []
    page_categories = set()
    for offset in range(0, 750, 100):
        page = learner_service.get_early_warning_page(
            dataset_id=DATASET_ID, dataset_ids=None, limit=100, offset=offset
        )
        assert page["total"] == 750
        assert page["offset"] == offset
        assert page["count"] == min(100, 750 - offset)
        assert page["has_more"] is (offset + page["count"] < 750)
        visited.extend(row["id"] for row in page["data"])
        page_categories.update(row["latest_risk_category"] for row in page["data"])

    assert len(visited) == 750
    assert len(set(visited)) == 750
    assert {"high", "medium", "low", None}.issubset(page_categories)
