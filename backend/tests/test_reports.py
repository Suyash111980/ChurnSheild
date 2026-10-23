import csv
import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.datasets import require_processed_dataset
from app.main import app
from app.repositories import learner_repository, recommendation_repository
from app.services import report_service


DATASET_ID = str(uuid4())


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def csv_rows(value):
    return list(csv.DictReader(io.StringIO(value)))


def test_risk_report_exports_only_persisted_predictions(monkeypatch):
    monkeypatch.setattr(learner_repository, "export_risk_predictions", lambda *_args, **_kwargs: SimpleNamespace(
        data=[{
            "external_learner_id": "00123", "code_module": "AAA", "code_presentation": "2014J",
            "latest_prediction_id": "prediction-1", "latest_model_version": "model-v1",
            "latest_risk_probability": 0.83, "latest_risk_category": "high",
            "latest_prediction_created_at": "2026-10-01T00:00:00Z",
        }], count=1,
    ))

    text, count = report_service.export_risk_analysis_csv(DATASET_ID)
    rows = csv_rows(text)

    assert count == 1
    assert rows[0]["learner_id"] == "00123"
    assert rows[0]["prediction_id"] == "prediction-1"
    assert rows[0]["model_version"] == "model-v1"
    assert rows[0]["risk_category"] == "high"


def test_risk_report_refuses_to_create_an_empty_success_file(monkeypatch):
    monkeypatch.setattr(learner_repository, "export_risk_predictions", lambda *_args, **_kwargs: SimpleNamespace(data=[], count=0))

    with pytest.raises(report_service.ReportUnavailable):
        report_service.export_risk_analysis_csv(DATASET_ID)


def test_recommendation_report_exports_persisted_associations_and_status(monkeypatch):
    monkeypatch.setattr(recommendation_repository, "export_dataset_recommendations", lambda *_args, **_kwargs: ([{
        "id": "recommendation-1", "learner_id": "learner-uuid", "prediction_id": "prediction-1",
        "rule_id": "low_vle_activity", "action": "Offer a check-in", "reason": "Saved rule evidence.",
        "status": "pending", "created_at": "2026-10-01T00:00:00Z", "updated_at": None,
        "learners": {"external_learner_id": "00123", "code_module": "AAA", "code_presentation": "2014J"},
    }], 1))

    text, count = report_service.export_recommendations_csv(DATASET_ID)
    row = csv_rows(text)[0]

    assert count == 1
    assert row["learner_id"] == "00123"
    assert row["code_module"] == "AAA"
    assert row["prediction_id"] == "prediction-1"
    assert row["rule_id"] == "low_vle_activity"
    assert row["status"] == "pending"


def test_risk_report_endpoint_is_admin_and_dataset_scoped(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}
    app.dependency_overrides[require_processed_dataset] = lambda: {"id": DATASET_ID, "status": "processed"}
    captured = {}

    def export(dataset_id):
        captured["dataset_id"] = dataset_id
        return "learner_id,risk_category\r\n00123,high\r\n", 1

    monkeypatch.setattr("app.api.routes.reports.export_risk_analysis_csv", export)
    response = TestClient(app).get(f"/api/v1/reports/risk-analysis.csv?dataset_id={DATASET_ID}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "churnshield-risk-analysis.csv" in response.headers["content-disposition"]
    assert response.text.endswith("00123,high\r\n")
    assert captured["dataset_id"] == DATASET_ID


def test_recommendation_report_endpoint_refuses_empty_export(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"app_role": "admin"}
    app.dependency_overrides[require_processed_dataset] = lambda: {"id": DATASET_ID, "status": "processed"}
    monkeypatch.setattr(
        "app.api.routes.reports.export_recommendations_csv",
        lambda _dataset_id: (_ for _ in ()).throw(report_service.ReportUnavailable("No saved recommendations are available.")),
    )

    response = TestClient(app).get(f"/api/v1/reports/recommendations.csv?dataset_id={DATASET_ID}")
    assert response.status_code == 409
    assert "No saved recommendations" in response.json()["detail"]
