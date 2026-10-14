from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import joblib

from ml.src.features.model_schema import CATEGORICAL_FEATURES, NUMERIC_FEATURES, RAW_FEATURES
from ml.src.inference.predict import predict_records
from ml.src.training.evaluate import evaluate_binary_model
from ml.src.training.split_data import split_dataset
from ml.src.training.train import train_models


def _records(students=120):
    rng = np.random.default_rng(51)
    rows = []
    for student in range(students):
        withdrawn = int(student % 3 == 0)
        for term in range(2):
            row = {
                "id_student": student,
                "code_module": "AAA" if term == 0 else "BBB",
                "code_presentation": "2014J" if student % 2 else "2014B",
                "gender": "F" if student % 2 else "M",
                "region": "Region A",
                "highest_education": "A Level",
                "imd_band": "10-20%",
                "age_band": "0-35",
                "disability": "N",
                "target_withdrawn": withdrawn,
            }
            for col in NUMERIC_FEATURES:
                row[col] = float(rng.integers(0, 25))
            row["vle_total_clicks_by_cutoff"] = 5 if withdrawn else 120
            rows.append(row)
    result = pd.DataFrame(rows)
    result["student_name"] = "Display Only"
    return result


def test_grouped_splits_are_reproducible_and_keep_students_separate():
    data = _records()
    a = split_dataset(data, 42)
    b = split_dataset(data, 42)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])
    groups = {key: set(data.iloc[index].id_student) for key, index in a.items()}
    assert not groups["train"] & groups["validation"]
    assert not groups["train"] & groups["test"]
    assert not groups["validation"] & groups["test"]


def test_train_saves_models_metrics_and_verified_ordered_schema(tmp_path):
    result = train_models(_records(), tmp_path, seed=42, n_estimators=20, n_jobs=1)
    directory = result["artifact_dir"]
    assert (directory / "random_forest_pipeline.joblib").is_file()
    assert (directory / "baseline_logistic_pipeline.joblib").is_file()
    schema = json.loads((directory / "feature_schema.json").read_text())
    evaluation = json.loads((directory / "evaluation.json").read_text())
    assert schema["raw_input_features"]
    assert schema["final_model_feature_count"] == len(schema["final_model_features"])
    trained = joblib.load(directory / "random_forest_pipeline.joblib")
    assert trained.named_steps["classifier"].n_features_in_ == schema["final_model_feature_count"]
    importance = json.loads((directory / "feature_importance.json").read_text())
    assert len(importance["features"]) == schema["final_model_feature_count"]
    assert "id_student" not in schema["final_model_features"]
    assert not any("student_name" in col for col in schema["final_model_features"])
    assert set(evaluation["models"]) == {"baseline_logistic", "random_forest"}
    for model_results in evaluation["models"].values():
        assert model_results["test"]["sample_count"] > 0
        assert 0 <= model_results["test"]["precision"] <= 1
        assert 0 <= model_results["test"]["recall"] <= 1
        assert 0 <= model_results["test"]["f1"] <= 1
        assert model_results["test"]["roc_auc"] is not None
        assert np.asarray(model_results["test"]["confusion_matrix_labels_0_1"]).shape == (2, 2)


def test_inference_handles_missing_values_unseen_categories_and_ignores_names(tmp_path):
    result = train_models(_records(), tmp_path, n_estimators=15, n_jobs=1)
    query = _records(2).drop(columns="target_withdrawn").iloc[:2].copy()
    query["code_module"] = "NEWMODULE"
    query["gender"] = None
    query["vle_total_clicks_by_cutoff"] = None
    predictions = predict_records(query, result["artifact_dir"])
    assert list(predictions.columns) == ["id_student", "code_module", "code_presentation", "predicted_class", "withdrawal_risk_probability", "model_version"]
    assert len(predictions) == 2
    assert predictions["predicted_class"].isin([0, 1]).all()
    assert predictions["withdrawal_risk_probability"].between(0, 1).all()
    assert "student_name" not in predictions


def test_inference_rejects_missing_required_features(tmp_path):
    result = train_models(_records(), tmp_path, n_estimators=10, n_jobs=1)
    with pytest.raises(ValueError, match="Missing required model input column"):
        predict_records(pd.DataFrame({"code_module": ["AAA"]}), result["artifact_dir"])


def test_inference_rejects_non_numeric_values_in_numeric_features(tmp_path):
    result = train_models(_records(), tmp_path, n_estimators=10, n_jobs=1)
    query = _records(2).drop(columns="target_withdrawn").iloc[:1].copy()
    query[NUMERIC_FEATURES[0]] = "not-a-number"
    with pytest.raises(ValueError, match="must contain numeric values"):
        predict_records(query, result["artifact_dir"])


def test_inference_rejects_infinite_numeric_values(tmp_path):
    result = train_models(_records(), tmp_path, n_estimators=10, n_jobs=1)
    query = _records(2).drop(columns="target_withdrawn").iloc[:1].copy()
    query[NUMERIC_FEATURES[0]] = np.inf
    with pytest.raises(ValueError, match="must contain finite numeric values"):
        predict_records(query, result["artifact_dir"])


def test_target_and_identifiers_are_not_raw_model_features():
    assert "target_withdrawn" not in RAW_FEATURES
    assert "id_student" not in RAW_FEATURES
    assert "student_name" not in RAW_FEATURES
    assert set(CATEGORICAL_FEATURES).isdisjoint(NUMERIC_FEATURES)


def test_metrics_use_withdrawal_as_positive_label():
    class FixedModel:
        def predict_proba(self, X):
            return np.array([[0.9, 0.1], [0.2, 0.8], [0.8, 0.2], [0.1, 0.9]])

    metrics = evaluate_binary_model(FixedModel(), np.zeros((4, 1)), [0, 1, 0, 1])
    assert metrics["positive_class"] == 1
    assert metrics["precision"] == 1
    assert metrics["recall"] == 1
    assert metrics["f1"] == 1
    assert metrics["roc_auc"] == 1
    assert metrics["confusion_matrix_labels_0_1"] == [[2, 0], [0, 2]]
