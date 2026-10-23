from types import SimpleNamespace

from app.repositories import dataset_repository, learner_repository
from app.services import dashboard_service


def test_course_insights_aggregate_saved_predictions_by_module_and_presentation(monkeypatch):
    monkeypatch.setattr(
        dataset_repository,
        "get_owned_dataset",
        lambda dataset_id, owner_id, workspace_id: {"id": dataset_id, "status": "processed"},
    )
    monkeypatch.setattr(
        learner_repository,
        "list_course_insight_rows",
        lambda dataset_id: [
            {"code_module": "AAA", "code_presentation": "2014J", "latest_prediction_id": "p1", "latest_risk_probability": 0.8, "latest_risk_category": "high"},
            {"code_module": "AAA", "code_presentation": "2014J", "latest_prediction_id": "p2", "latest_risk_probability": 0.2, "latest_risk_category": "low"},
            {"code_module": "BBB", "code_presentation": "2014B", "latest_prediction_id": None, "latest_risk_probability": None, "latest_risk_category": None},
        ],
    )

    result = dashboard_service.get_course_insights("dataset", "owner", "workspace")

    assert result["learner_course_records"] == 3
    assert result["course_presentation_count"] == 2
    assert result["learners_with_prediction"] == 2
    assert result["courses"][0] == {
        "code_module": "AAA",
        "code_presentation": "2014J",
        "learner_course_records": 2,
        "learners_with_prediction": 2,
        "low_risk_count": 1,
        "medium_risk_count": 0,
        "high_risk_count": 1,
        "prediction_coverage": 1.0,
        "average_risk_probability": 0.5,
    }
    assert result["courses"][1]["prediction_coverage"] == 0.0
    assert result["courses"][1]["average_risk_probability"] is None
    assert result["weekly_activity_available"] is False


def test_course_insights_do_not_convert_an_uncategorized_prediction_into_missing_or_low(monkeypatch):
    monkeypatch.setattr(dataset_repository, "get_owned_dataset", lambda *_args: {"status": "processed"})
    monkeypatch.setattr(learner_repository, "list_course_insight_rows", lambda *_args: [
        {"code_module": "AAA", "code_presentation": "2014J", "latest_prediction_id": "p1", "latest_risk_probability": None, "latest_risk_category": None},
        {"code_module": "AAA", "code_presentation": "2014J", "latest_prediction_id": None, "latest_risk_probability": None, "latest_risk_category": None},
    ])

    result = dashboard_service.get_course_insights("dataset", "owner", "workspace")

    course = result["courses"][0]
    assert course["learner_course_records"] == 2
    assert course["learners_with_prediction"] == 1
    assert course["prediction_coverage"] == 0.5
    assert course["low_risk_count"] == course["medium_risk_count"] == course["high_risk_count"] == 0
    assert course["average_risk_probability"] is None


def test_course_insights_are_scoped_to_owned_dataset(monkeypatch):
    monkeypatch.setattr(dataset_repository, "get_owned_dataset", lambda *_args: None)
    monkeypatch.setattr(
        learner_repository,
        "list_course_insight_rows",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not query rows for unowned dataset")),
    )

    assert dashboard_service.get_course_insights("dataset", "owner", "workspace") is None


def test_course_insight_rows_paginate_until_last_page(monkeypatch):
    class Query:
        def __init__(self, offset):
            self.offset = offset

        def select(self, *_args): return self
        def eq(self, *_args): return self
        def order(self, *_args): return self
        def range(self, start, _end):
            self.offset = start
            return self
        def execute(self):
            rows = ([{"id": str(i)} for i in range(3)] if self.offset == 0 else [{"id": "3"}])
            return SimpleNamespace(data=rows)

    class Client:
        def table(self, _name):
            return Query(0)

    monkeypatch.setattr(learner_repository, "supabase", Client())

    rows = learner_repository.list_course_insight_rows("dataset", page_size=3)
    assert [row["id"] for row in rows] == ["0", "1", "2", "3"]
