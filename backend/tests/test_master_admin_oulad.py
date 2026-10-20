import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_roles
from app.api.routes import master_admin


def test_oulad_overview_reports_real_local_rows_and_evaluation(tmp_path, monkeypatch):
    data_path = tmp_path / "prepared.csv"
    data_path.write_text(
        "id_student,code_module,code_presentation,target_withdrawn,feature_value\n"
        "1,AAA,2014J,0,0.25\n1,AAA,2014J,1,0.5\n2,BBB,2014B,1,0.75\n",
        encoding="utf-8",
    )

    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"test artifact marker")
    artifact.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "model_version": "test-v1",
                "target": "target_withdrawn",
                "positive_class": "Withdrawn",
                "feature_columns": ["feature_value"],
                "split": {
                    "method": "grouped",
                    "row_counts": {"train": 2, "validation": 1, "test": 3},
                },
                "prepared_cohort": {"rows": 6},
                "model_configuration": {"n_estimators": 300},
            }
        ),
        encoding="utf-8",
    )
    artifact.with_suffix(".evaluation.json").write_text(
        json.dumps({"test": {"precision": 0.8, "record_count": 3}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        master_admin,
        "settings",
        SimpleNamespace(
            model_path=str(artifact),
            resolve_backend_path=lambda value: (
                data_path if "processed" in value else artifact
            ),
        ),
    )
    monkeypatch.setattr(master_admin, "feature_columns", lambda: ["feature_value"])
    monkeypatch.setattr(master_admin, "get_model", lambda: SimpleNamespace())
    monkeypatch.setattr(master_admin, "validate_model_features", lambda model, names: None)
    monkeypatch.setattr(
        master_admin,
        "predict_records",
        lambda records, *, record_ids: [
            {
                "record_id": record_ids[0],
                "risk_probability": 0.25,
                "risk_category": "low",
                "model_version": "test-v1",
            }
        ] if len(records) == 1 else [],
    )

    result = master_admin.oulad_overview(
        _master={"app_role": "master_admin"}
    )

    assert result["dataset"]["status"] == "prepared_locally_not_imported"
    assert result["dataset"]["record_count"] == 3
    assert result["dataset"]["learner_course_presentation_count"] == 2
    assert result["dataset"]["target_withdrawal_distribution"] == {
        "1": 2,
        "0": 1,
    }
    assert result["dataset"]["imported_to_supabase"] is False
    assert result["dataset"]["storage_type"] == "local_csv"
    assert result["dataset"]["storage_location"] == "ml/data/processed/oulad_learner_features.csv"
    assert result["model"]["version"] == "test-v1"
    assert result["model"]["evaluation"]["precision"] == 0.8
    assert result["model"]["artifact_available"] is True
    assert result["model"]["artifact_load_status"] == "loaded"
    assert result["model"]["metadata_status"] == "available"
    assert result["model"]["feature_count"] == 1
    assert result["model"]["training"] == {
        "prepared_cohort_rows": 6,
        "train_rows": 2,
        "validation_rows": 1,
        "test_rows": 3,
        "training_date": None,
        "duration_seconds": None,
    }
    assert result["model"]["inference"] == {
        "status": "sample_scored",
        "persisted": False,
        "full_dataset_status": "not_generated",
        "full_dataset_persisted": False,
        "full_dataset_prediction_count": None,
        "model_version": "test-v1",
    }
    assert result["model"]["recommendations"]["generation_status"] == "not_implemented"


def test_missing_oulad_data_and_artifacts_return_honest_unavailable_status(
    tmp_path, monkeypatch
):
    artifact = tmp_path / "missing.joblib"

    monkeypatch.setattr(
        master_admin,
        "settings",
        SimpleNamespace(
            model_path=str(artifact),
            resolve_backend_path=lambda value: (
                tmp_path / "missing.csv" if "processed" in value else artifact
            ),
        ),
    )

    result = master_admin.oulad_overview(
        _master={"app_role": "master_admin"}
    )

    assert result["dataset"]["status"] == "not_available"
    assert result["dataset"].get("record_count") is None
    assert result["model"]["artifact_available"] is False
    assert result["model"]["artifact_load_status"] == "unavailable"
    assert result["model"]["metadata_status"] == "not_available"
    assert result["model"]["evaluation_available"] is False
    assert result["model"]["inference"]["persisted"] is False


def test_present_artifact_is_not_reported_as_loaded_when_loading_fails(tmp_path, monkeypatch):
    artifact = tmp_path / "unreadable.joblib"
    artifact.write_bytes(b"not a model")
    monkeypatch.setattr(
        master_admin,
        "settings",
        SimpleNamespace(
            model_path=str(artifact),
            resolve_backend_path=lambda value: tmp_path / "missing.csv" if "processed" in value else artifact,
        ),
    )
    monkeypatch.setattr(master_admin, "get_model", lambda: (_ for _ in ()).throw(master_admin.ModelArtifactError("unreadable")))

    result = master_admin.oulad_overview(_master={"app_role": "master_admin"})

    assert result["model"]["artifact_available"] is True
    assert result["model"]["artifact_load_status"] == "unavailable"
    assert result["model"]["metadata_status"] == "not_available"
    assert result["model"]["evaluation_status"] == "not_available"


@pytest.mark.parametrize("role", ["admin", "retention_manager", "data_analyst"])
def test_workspace_roles_cannot_access_oulad_overview(role):
    master_only = require_roles("master_admin")
    with pytest.raises(HTTPException) as error:
        master_only(current_user={"app_role": role})
    assert error.value.status_code == 403


def test_master_admin_role_is_allowed_for_master_admin_dependency():
    master_only = require_roles("master_admin")
    master = {"app_role": "master_admin"}
    assert master_only(current_user=master) == master
