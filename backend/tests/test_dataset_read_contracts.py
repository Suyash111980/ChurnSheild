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
        lambda *_args: {"id": DATASET_ID},
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
