"""Local service-contract checks for the three dataset workspace APIs."""

from types import SimpleNamespace

from app.repositories import dataset_repository, learner_repository, prediction_repository
from app.schemas.dashboard import DashboardSummary
from app.schemas.learner import LearnerPage
from app.schemas.recommendation import EarlyWarningPage
from app.services import dashboard_service, learner_service


DATASET_ID = "dataset-local-test"


def test_dashboard_summary_matches_dataset_workspace_response(monkeypatch):
    monkeypatch.setattr(
        dataset_repository,
        "get_owned_dataset",
        lambda *_args: {"id": DATASET_ID, "status": "processed"},
    )
    monkeypatch.setattr(
        dataset_repository,
        "get_dashboard_summary",
        lambda _dataset_id: {
            "total_learner_records": 2,
            "course_presentation_count": 1,
            "learners_with_prediction": 1,
            "low_risk_count": 0,
            "medium_risk_count": 0,
            "high_risk_count": 1,
        },
    )

    result = dashboard_service.get_summary(DATASET_ID, "owner", "workspace")
    response = DashboardSummary.model_validate(result)

    assert response.dataset_id == DATASET_ID
    assert response.total_learner_records == 2
    assert response.prediction_coverage == 0.5
    assert response.risk_distribution == {"low": 0, "medium": 0, "high": 1}
    assert response.prediction_state == "available"


def test_all_dataset_summary_aggregates_only_persisted_authorized_summaries(monkeypatch):
    datasets = [
        {"id": "d1", "status": "processed", "dataset_name": "Course A"},
        {"id": "d2", "status": "processed", "dataset_name": "Course B"},
        {"id": "queued", "status": "processing", "dataset_name": "Queued"},
    ]
    monkeypatch.setattr(dataset_repository, "list_all_owned_datasets", lambda **_kwargs: datasets)
    summaries = [
        {
            "dataset_id": "d1", "total_learner_records": 3,
            "course_presentation_count": 1, "learners_with_prediction": 2,
            "low_risk_count": 1, "medium_risk_count": 0, "high_risk_count": 1,
        },
        {
            "dataset_id": "d2", "total_learner_records": 2,
            "course_presentation_count": 1, "learners_with_prediction": 0,
            "low_risk_count": 0, "medium_risk_count": 0, "high_risk_count": 0,
        },
    ]
    monkeypatch.setattr(dataset_repository, "get_dashboard_summaries", lambda ids: summaries)
    monkeypatch.setattr(
        learner_repository,
        "list_course_insight_rows",
        lambda *_args, **_kwargs: [
            {"code_module": "AAA", "code_presentation": "2014J"},
            {"code_module": "AAA", "code_presentation": "2014J"},
        ],
    )

    result = dashboard_service.get_summary("all", "owner", "workspace")

    assert result["total_learner_records"] == 5
    assert result["learners_with_prediction"] == 2
    assert result["prediction_coverage"] == 0.4
    assert result["risk_distribution"] == {"low": 1, "medium": 0, "high": 1}
    assert result["dataset_count"] == 2
    assert result["course_presentation_count"] == 1
    assert [row["dataset_name"] for row in result["dataset_comparison"]] == ["Course A", "Course B"]
    assert result["dataset_comparison"][1]["prediction_coverage"] == 0


def test_all_dataset_summary_treats_a_processed_empty_dataset_as_zero(monkeypatch):
    monkeypatch.setattr(
        dataset_repository,
        "list_all_owned_datasets",
        lambda **_kwargs: [{"id": "empty", "status": "processed", "dataset_name": "Empty"}],
    )
    monkeypatch.setattr(dataset_repository, "get_dashboard_summaries", lambda _ids: [])
    monkeypatch.setattr(learner_repository, "list_course_insight_rows", lambda *_args, **_kwargs: [])

    result = dashboard_service.get_summary("all", "owner", "workspace")

    assert result["dataset_count"] == 1
    assert result["total_learner_records"] == 0
    assert result["learners_with_prediction"] == 0
    assert result["prediction_coverage"] is None
    assert result["risk_distribution"] is None
    assert result["dataset_comparison"][0]["learner_course_records"] == 0


def test_learner_page_matches_frontend_fields_and_pagination(monkeypatch):
    monkeypatch.setattr(
        learner_repository,
        "list_learners",
        lambda **_filters: SimpleNamespace(
            data=[{
                "id": "learner-local-test",
                "external_learner_id": "00123",
                "code_module": "AAA",
                "code_presentation": "2014J",
                "latest_risk_probability": 0.73,
                "latest_risk_category": "high",
                "dataset_id": DATASET_ID,
            }],
            count=1,
        ),
    )
    monkeypatch.setattr(
        learner_service,
        "attach_student_names",
        lambda rows: [{**row, "student_name": None} for row in rows],
    )

    result = learner_service.list_learners(
        limit=20, offset=0, dataset_id=DATASET_ID
    )
    response = LearnerPage.model_validate(result)

    assert response.total == response.count == 1
    assert response.data[0]["id_student"] == "00123"
    assert response.data[0]["latest_risk_probability"] == 0.73
    assert response.data[0]["latest_risk_category"] == "high"
    assert response.has_more is False


def test_all_dataset_learner_query_is_scoped_and_uses_database_filters(monkeypatch):
    class Query:
        def __init__(self):
            self.filters = []
            self.orders = []
            self.page = None

        def select(self, *_args, **_kwargs): return self
        def in_(self, field, values): self.filters.append((field, values)); return self
        def eq(self, field, value): self.filters.append((field, value)); return self
        def or_(self, expression): self.filters.append(("or", expression)); return self
        def order(self, field, **kwargs): self.orders.append((field, kwargs)); return self
        def range(self, start, end): self.page = (start, end); return self
        def execute(self): return SimpleNamespace(data=[], count=0)

    class Database:
        def __init__(self): self.query = Query()
        def table(self, _name): return self.query

    database = Database()
    monkeypatch.setattr(learner_repository, "supabase", database)

    result = learner_repository.list_learners(
        dataset_id=None, dataset_ids=["d1", "d2"], limit=10, offset=20,
        search="001", code_module="AAA", risk_category="high",
        sort="latest_risk_probability", direction="desc",
    )

    assert result.count == 0
    assert ("dataset_id", ["d1", "d2"]) in database.query.filters
    assert ("code_module", "AAA") in database.query.filters
    assert ("latest_risk_category", "high") in database.query.filters
    assert ("or", "external_learner_id.ilike.%001%,code_module.ilike.%001%,code_presentation.ilike.%001%") in database.query.filters
    assert database.query.orders[0][0] == "latest_risk_probability"
    assert database.query.orders[0][1]["desc"] is True
    assert database.query.page == (20, 29)


def test_early_warning_page_matches_frontend_and_keeps_missing_risk_empty(monkeypatch):
    monkeypatch.setattr(
        learner_repository,
        "list_early_warning",
        lambda **_filters: SimpleNamespace(
            data=[{
                "id": "learner-local-test",
                "id_student": "00123",
                "code_module": "AAA",
                "code_presentation": "2014J",
                "latest_prediction_id": None,
                "latest_risk_probability": None,
                "latest_risk_category": None,
            }],
            count=1,
        ),
    )
    monkeypatch.setattr(learner_repository, "get_latest_feature_snapshots", lambda *_args: [])
    monkeypatch.setattr(learner_repository, "get_latest_recommendations", lambda *_args: [])
    monkeypatch.setattr(prediction_repository, "list_explanations_for_predictions", lambda *_args: [])
    monkeypatch.setattr(learner_service, "get_student_name", lambda _row: None)

    result = learner_service.get_early_warning_page(
        dataset_id=DATASET_ID, limit=20, offset=0
    )
    response = EarlyWarningPage.model_validate(result)

    assert response.total == 1
    assert response.data[0]["prediction_state"] == "unavailable"
    assert response.data[0]["latest_risk_probability"] is None
    assert response.data[0]["latest_risk_category"] is None
    assert response.data[0]["latest_explanations"] == []


def test_all_dataset_early_warning_enrichment_stays_within_authorized_dataset_ids(monkeypatch):
    first_id, second_id = "learner-1", "learner-2"
    dataset_ids = ["authorized-a", "authorized-b"]
    rows = [
        {"id": first_id, "dataset_id": dataset_ids[0], "latest_prediction_id": "prediction-1", "latest_risk_category": "high"},
        {"id": second_id, "dataset_id": dataset_ids[1], "latest_prediction_id": None, "latest_risk_category": None},
    ]
    scopes = {}
    monkeypatch.setattr(learner_repository, "list_early_warning", lambda **_filters: SimpleNamespace(data=rows, count=2))
    monkeypatch.setattr(learner_repository, "get_latest_feature_snapshots", lambda _ids, _id, ids: scopes.update(features=ids) or [])
    monkeypatch.setattr(learner_repository, "get_latest_recommendations", lambda _ids, _id, ids: scopes.update(recommendations=ids) or [])
    monkeypatch.setattr(prediction_repository, "list_explanations_for_predictions", lambda _ids, _id, ids: scopes.update(explanations=ids) or [])
    monkeypatch.setattr(learner_service, "get_student_name", lambda _row: None)

    result = learner_service.get_early_warning_page(
        dataset_id=None, dataset_ids=dataset_ids, limit=20, offset=0
    )

    assert len(result["data"]) == 2
    assert [row["dataset_id"] for row in result["data"]] == dataset_ids
    assert result["data"][1]["prediction_state"] == "unavailable"
    assert result["data"][1]["latest_risk_category"] is None
    assert scopes == {"features": dataset_ids, "recommendations": dataset_ids, "explanations": dataset_ids}
