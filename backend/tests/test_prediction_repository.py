
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories import prediction_repository


PREDICTION_ID = str(uuid4())
DATASET_ID = str(uuid4())
OTHER_DATASET_ID = str(uuid4())


class FakeQuery:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.table_name = None
        self.selected = None
        self.filters = []
        self.in_filters = []
        self.orders = []
        self.requested_range = None
        self.limit_value = None

    def table(self, table_name):
        self.table_name = table_name
        return self

    def select(self, columns, **_kwargs):
        self.selected = columns
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def in_(self, field, values):
        self.in_filters.append((field, list(values)))
        return self

    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self

    def range(self, first, last):
        self.requested_range = (first, last)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows, count=len(self.rows))


def test_get_prediction_filters_by_prediction_and_dataset(monkeypatch):
    fake = FakeQuery(
        [
            {
                "id": PREDICTION_ID,
                "learner_id": str(uuid4()),
            }
        ]
    )
    monkeypatch.setattr(prediction_repository, "supabase", fake)

    result = prediction_repository.get_prediction(PREDICTION_ID, DATASET_ID)

    assert result["id"] == PREDICTION_ID
    assert fake.table_name == "predictions"
    assert "learners!inner" in fake.selected
    assert ("id", PREDICTION_ID) in fake.filters
    assert ("learners.dataset_id", DATASET_ID) in fake.filters
    assert fake.limit_value == 1


def test_list_predictions_filters_by_dataset(monkeypatch):
    fake = FakeQuery([{"id": PREDICTION_ID}])
    monkeypatch.setattr(prediction_repository, "supabase", fake)

    result = prediction_repository.list_predictions(
        dataset_id=DATASET_ID,
        limit=10,
        offset=5,
    )

    assert result.data == [{"id": PREDICTION_ID}]
    assert fake.table_name == "predictions"
    assert ("learners.dataset_id", DATASET_ID) in fake.filters
    assert fake.requested_range == (5, 14)


def test_explanations_filter_by_prediction_ids_and_dataset(monkeypatch):
    fake = FakeQuery(
        [
            {
                "prediction_id": PREDICTION_ID,
                "feature_name": "clicks",
            }
        ]
    )
    monkeypatch.setattr(prediction_repository, "supabase", fake)

    result = prediction_repository.list_explanations_for_predictions(
        [PREDICTION_ID],
        DATASET_ID,
    )

    assert result[0]["prediction_id"] == PREDICTION_ID
    assert fake.table_name == "risk_explanations"
    assert "predictions!inner" in fake.selected
    assert ("prediction_id", [PREDICTION_ID]) in fake.in_filters
    assert (
        "predictions.learners.dataset_id",
        DATASET_ID,
    ) in fake.filters
    assert fake.limit_value == 2500


def test_explanations_with_no_prediction_ids_skip_database(monkeypatch):
    def fail_if_called():
        pytest.fail("Database should not be queried for an empty ID list")

    class FakeDatabase:
        def table(self, _table_name):
            pytest.fail("Database should not be queried for an empty ID list")

    monkeypatch.setattr(
        prediction_repository,
        "supabase",
        FakeDatabase(),
    )

    assert (
        prediction_repository.list_explanations_for_predictions([], DATASET_ID)
        == []
    )
