"""Isolated tests for prepared-dataset inference and prediction persistence."""

import csv
import io

from app.integrations.feature_contract import feature_columns
from app.integrations.ml_loader import ModelArtifactError
from app.repositories import dataset_repository
from app.services import dataset_service
from app.utils.dataset_parser import parse_dataset


OWNER_ID = "owner-1"
WORKSPACE_ID = "workspace-1"
DATASET_ID = "dataset-1"


def prepared_csv() -> bytes:
    row = {
        "id_student": "00123",
        "code_module": "AAA",
        "code_presentation": "2014J",
        "target_withdrawn": "1",
        "final_result": "Withdrawn",
    }
    row.update({column: "1" for column in feature_columns() if column not in row})
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue().encode("utf-8")


class PredictionTable:
    """Mock upsert storage that follows the migration 007 conflict contract."""

    def __init__(self):
        self.rows = {}
        self.payload = []
        self.conflict = None

    def table(self, name):
        assert name == "predictions"
        return self

    def upsert(self, records, *, on_conflict):
        from uuid import NAMESPACE_URL, uuid5

        self.conflict = on_conflict
        for record in records:
            key = (record["learner_id"], record["model_version"])
            self.rows[key] = {
                **record,
                "id": str(uuid5(NAMESPACE_URL, "|".join(key))),
            }
        self.payload = [self.rows[(record["learner_id"], record["model_version"])] for record in records]
        return self

    def select(self, _columns):
        return self

    def execute(self):
        return type("Response", (), {"data": list(self.payload)})()


def configure_mock_processing(monkeypatch, *, predictions=None):
    updates = []
    learners = []
    feature_batches = []
    def upsert_learners(records):
        learners.extend(records)
        return [
            {
                "id": "learner-uuid",
                "dataset_id": DATASET_ID,
                "external_learner_id": record["external_learner_id"],
                "code_module": record["code_module"],
                "code_presentation": record["code_presentation"],
            }
            for record in records
        ]

    monkeypatch.setattr(dataset_repository, "upsert_learners", upsert_learners)
    monkeypatch.setattr(
        dataset_repository,
        "upsert_features",
        lambda records: feature_batches.append(records),
    )
    monkeypatch.setattr(dataset_service, "explain_records", lambda rows: [[] for _ in rows])
    monkeypatch.setattr(dataset_service, "recommend_records", lambda rows: [[] for _ in rows])
    monkeypatch.setattr(dataset_repository, "upsert_explanations", lambda records: records)
    monkeypatch.setattr(
        dataset_repository,
        "upsert_recommendations",
        lambda records, *, dataset_id: {"persisted": records, "failed_count": 0},
    )
    monkeypatch.setattr(
        dataset_repository,
        "update_owned_dataset",
        lambda dataset_id, owner_id, workspace_id, changes: (
            updates.append((dataset_id, owner_id, workspace_id, changes))
            or {"id": dataset_id, "status": changes.get("status", "processing"), **changes}
        ),
    )
    if predictions is not None:
        monkeypatch.setattr(dataset_service, "predict_records", predictions)
    return updates, learners, feature_batches


def test_prepared_dataset_runs_approved_inference_and_persists_idempotently(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    assert parsed.report["prediction_compatible"] is True

    store = PredictionTable()
    monkeypatch.setattr(dataset_repository, "supabase", store)
    updates, learners, feature_batches = configure_mock_processing(monkeypatch)
    inference_calls = []

    def approved_inference(records, *, record_ids):
        inference_calls.append((records, record_ids))
        return [{
            "record_id": record_ids[0],
            "model_version": "approved-test-v1",
            "risk_probability": 0.73,
            "risk_category": "high",
            "predicted_at": "2026-10-17T00:00:00+00:00",
        }]

    monkeypatch.setattr(dataset_service, "predict_records", approved_inference)

    def process_once():
        return dataset_service._process_parsed_dataset(
            dataset_id=DATASET_ID,
            owner_id=OWNER_ID,
            workspace_id=WORKSPACE_ID,
            parsed=parsed,
            initial_record={"id": DATASET_ID},
        )

    first = process_once()
    second = process_once()

    assert first["validation"]["prediction_state"] == "available"
    assert first["validation"]["predictions_persisted"] == 1
    assert second["validation"]["predictions_persisted"] == 1
    assert len(store.rows) == 1
    assert store.conflict == "learner_id,model_version"
    assert len(inference_calls) == 2
    features, record_ids = inference_calls[0]
    assert record_ids == ["learner-uuid"]
    assert list(features[0]) == feature_columns()
    assert "target_withdrawn" not in features[0]
    assert "final_result" not in features[0]
    assert learners[0]["external_learner_id"] == "00123"
    assert learners[0]["dataset_id"] == DATASET_ID
    assert feature_batches[0][0]["learner_id"] == "learner-uuid"
    assert all(
        dataset_id == DATASET_ID and owner_id == OWNER_ID and workspace_id == WORKSPACE_ID
        for dataset_id, owner_id, workspace_id, _changes in updates
    )


def test_model_loading_failure_marks_dataset_failed_and_writes_no_prediction(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    store = PredictionTable()
    monkeypatch.setattr(dataset_repository, "supabase", store)
    configure_mock_processing(monkeypatch)

    def disabled_inference(_records, *, record_ids):
        raise ModelArtifactError("Model inference is disabled until a model version is approved.")

    monkeypatch.setattr(dataset_service, "predict_records", disabled_inference)
    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID,
        owner_id=OWNER_ID,
        workspace_id=WORKSPACE_ID,
        parsed=parsed,
        initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "failed"
    assert result["data"]["error_summary"]
    assert result["validation"]["prediction_state"] == "failed"
    assert result["validation"]["processing_state"] == "failed"
    assert result["validation"]["failed_stage"] == "preprocessing_and_inference"
    assert result["validation"]["prediction_error_code"] == "model_unavailable"
    assert result["validation"]["prediction_message"]
    assert result["validation"]["predictions_persisted"] == 0
    assert store.rows == {}


def test_feature_persistence_failure_marks_dataset_failed_at_last_confirmed_progress(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    updates = []
    configure_mock_processing(monkeypatch)
    monkeypatch.setattr(
        dataset_repository, "upsert_features",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("provider details remain private")),
    )
    monkeypatch.setattr(
        dataset_repository, "update_owned_dataset",
        lambda dataset_id, _owner, _workspace, changes: (
            updates.append(changes.copy())
            or {"id": dataset_id, "status": changes.get("status", "processing"), **changes}
        ),
    )
    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID, owner_id=OWNER_ID, workspace_id=WORKSPACE_ID,
        parsed=parsed, initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "failed"
    assert result["data"]["processing_progress"] == 65
    assert "provider details remain private" not in result["data"]["error_summary"]
    assert result["validation"]["failed_stage"] == "feature_persistence"
    assert result["validation"]["prediction_state"] == "failed"
    assert result["validation"]["prediction_error_code"] == "feature_persistence_failed"


def test_prediction_persistence_failure_marks_dataset_failed_and_saves_no_success(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    configure_mock_processing(monkeypatch)
    monkeypatch.setattr(
        dataset_repository, "upsert_predictions",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("provider row values must not leak")),
    )
    monkeypatch.setattr(
        dataset_service, "predict_records",
        lambda _rows, *, record_ids: [{
            "record_id": record_ids[0], "model_version": "approved-test-v1",
            "risk_probability": 0.7, "risk_category": "high",
            "predicted_at": "2026-10-17T00:00:00+00:00",
        }],
    )

    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID, owner_id=OWNER_ID, workspace_id=WORKSPACE_ID,
        parsed=parsed, initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "failed"
    assert result["validation"]["failed_stage"] == "prediction_persistence"
    assert result["validation"]["prediction_state"] == "failed"
    assert result["validation"]["prediction_error_code"] == "prediction_persistence_failed"
    assert result["validation"]["predictions_persisted"] == 0
    assert "provider row values must not leak" not in result["data"]["error_summary"]


def test_inference_runtime_failure_is_reported_as_failed_not_not_started(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    store = PredictionTable()
    monkeypatch.setattr(dataset_repository, "supabase", store)
    configure_mock_processing(monkeypatch)

    def broken_inference(_records, *, record_ids):
        raise RuntimeError("model runtime failed")

    monkeypatch.setattr(dataset_service, "predict_records", broken_inference)
    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID,
        owner_id=OWNER_ID,
        workspace_id=WORKSPACE_ID,
        parsed=parsed,
        initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "failed"
    assert result["validation"]["processing_state"] == "failed"
    assert result["validation"]["prediction_state"] == "failed"
    assert result["validation"]["failed_stage"] == "preprocessing_and_inference"
    assert "generation failed" in result["validation"]["prediction_error"]
    assert result["validation"]["predictions_persisted"] == 0
    assert store.rows == {}


def test_auxiliary_persistence_failures_do_not_misreport_saved_predictions(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    store = PredictionTable()
    monkeypatch.setattr(dataset_repository, "supabase", store)
    configure_mock_processing(monkeypatch)
    monkeypatch.setattr(
        dataset_service,
        "predict_records",
        lambda _records, *, record_ids: [{
            "record_id": record_ids[0], "model_version": "approved-test-v1",
            "risk_probability": 0.7, "risk_category": "high",
            "predicted_at": "2026-10-17T00:00:00+00:00",
        }],
    )
    monkeypatch.setattr(dataset_service, "explain_records", lambda rows: [[] for _ in rows])
    monkeypatch.setattr(dataset_service, "recommend_records", lambda _rows: [[{
        "rule_id": "assessment_without_submission_recorded_by_cutoff",
        "action": "Check whether assessment support would be useful.",
        "evidence": {
            "feature": "assessments_without_submission_recorded_by_cutoff",
            "observed_value": 1,
            "interpretation": "A due assessment had no submission recorded by cutoff.",
        },
        "requires_human_review": True,
    }]])
    monkeypatch.setattr(
        dataset_repository, "upsert_explanations",
        lambda _records: (_ for _ in ()).throw(RuntimeError("explanation store failed")),
    )
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("recommendation store failed")),
    )

    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID, owner_id=OWNER_ID, workspace_id=WORKSPACE_ID,
        parsed=parsed, initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "processed"
    assert result["validation"]["prediction_state"] == "available"
    assert result["validation"]["predictions_persisted"] == 1
    assert result["validation"]["explanations_state"] == "unavailable"
    assert result["validation"]["recommendations_state"] == "unavailable"


def test_auxiliary_generation_failures_do_not_misreport_saved_predictions(monkeypatch):
    parsed = parse_dataset("prepared.csv", prepared_csv())
    store = PredictionTable()
    monkeypatch.setattr(dataset_repository, "supabase", store)
    configure_mock_processing(monkeypatch)
    monkeypatch.setattr(
        dataset_service,
        "predict_records",
        lambda _records, *, record_ids: [{
            "record_id": record_ids[0], "model_version": "approved-test-v1",
            "risk_probability": 0.7, "risk_category": "high",
            "predicted_at": "2026-10-17T00:00:00+00:00",
        }],
    )
    monkeypatch.setattr(
        dataset_service, "explain_records",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("explanation generation failed")),
    )
    monkeypatch.setattr(
        dataset_service, "recommend_records",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("recommendation generation failed")),
    )

    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID, owner_id=OWNER_ID, workspace_id=WORKSPACE_ID,
        parsed=parsed, initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "processed"
    assert result["validation"]["prediction_state"] == "available"
    assert result["validation"]["predictions_persisted"] == 1
    assert result["validation"]["explanations_state"] == "unavailable"
    assert result["validation"]["explanations_failed"] == 1
    assert result["validation"]["recommendations_state"] == "unavailable"
    assert result["validation"]["recommendations_failed"] == 1
    assert len(store.rows) == 1


def test_missing_features_are_not_sent_to_inference(monkeypatch):
    content = prepared_csv().decode("utf-8")
    parsed = parse_dataset("prepared.csv", content.replace("vle_total_clicks_by_cutoff", "vle_clicks_removed").encode())
    assert parsed.report["prediction_compatible"] is False
    assert "vle_total_clicks_by_cutoff" in parsed.report["missing_prediction_columns"]

    calls = []
    configure_mock_processing(monkeypatch, predictions=lambda *args, **kwargs: calls.append(args))
    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID,
        owner_id=OWNER_ID,
        workspace_id=WORKSPACE_ID,
        parsed=parsed,
        initial_record={"id": DATASET_ID},
    )

    assert result["validation"]["prediction_state"] == "dataset_incompatible"
    assert result["validation"]["processing_state"] == "descriptive_only"
    assert result["validation"]["prediction_error_code"] == "required_features_missing"
    assert "vle_total_clicks_by_cutoff" in result["validation"]["prediction_message"]
    assert calls == []


def test_3000_row_descriptive_dataset_is_saved_without_fabricated_predictions(monkeypatch):
    output = io.StringIO(newline="")
    fields = ["id_student", "code_module", "code_presentation", "num_of_prev_attempts", "studied_credits", "TotalClicks"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for index in range(3000):
        writer.writerow({
            "id_student": f"synthetic-{index:04d}", "code_module": "AAA",
            "code_presentation": "2014J", "num_of_prev_attempts": 0,
            "studied_credits": 60, "TotalClicks": index,
        })
    parsed = parse_dataset("synthetic-descriptive.csv", output.getvalue().encode())
    assert parsed.report["row_count"] == 3000
    assert parsed.report["prediction_compatible"] is False

    updates = []
    prediction_calls = []
    monkeypatch.setattr(
        dataset_repository, "upsert_learners",
        lambda records: [
            {
                "id": f"learner-{record['external_learner_id']}", "dataset_id": DATASET_ID,
                "external_learner_id": record["external_learner_id"],
                "code_module": record["code_module"], "code_presentation": record["code_presentation"],
            }
            for record in records
        ],
    )
    monkeypatch.setattr(dataset_repository, "upsert_features", lambda _records: None)
    monkeypatch.setattr(dataset_repository, "update_owned_dataset", lambda *args: (
        updates.append(args[-1]) or {"id": DATASET_ID, "status": args[-1].get("status", "processing")}
    ))
    monkeypatch.setattr(dataset_service, "predict_records", lambda *args, **kwargs: prediction_calls.append(args))

    result = dataset_service._process_parsed_dataset(
        dataset_id=DATASET_ID, owner_id=OWNER_ID, workspace_id=WORKSPACE_ID,
        parsed=parsed, initial_record={"id": DATASET_ID},
    )

    assert result["data"]["status"] == "processed"
    assert result["validation"]["prediction_state"] == "dataset_incompatible"
    assert result["validation"]["prediction_error_code"] == "required_features_missing"
    assert result["validation"]["predictions_persisted"] == 0
    assert prediction_calls == []
    assert updates[-1]["row_count"] == 3000
