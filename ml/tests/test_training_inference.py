import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from ml.src.features.build_features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    validate_feature_frame,
)
from ml.src.inference.predict import InferenceContractError, load_inference_artifact, predict_records
from ml.src.inference.risk_categories import risk_category
from ml.src.explainability.shap_explainer import explain_with_shap
from ml.src.training.evaluate import evaluate_probabilities
from ml.src.training.split_data import grouped_train_validation_test_indices
from ml.src.training.train import train_baseline


def _training_rows():
    rows = []
    for learner in range(90):
        label = learner % 2
        for presentation in ("2014J", "2014B"):
            row = {
                "id_student": f"{learner:04d}",
                "code_module": "AAA" if learner % 3 else "BBB",
                "code_presentation": presentation,
                "target_withdrawn": label,
            }
            for index, name in enumerate(NUMERIC_FEATURES):
                row[name] = float(learner % 7 + index + label)
            row["vle_total_clicks_by_cutoff"] = float(1 if label else 100)
            rows.append(row)
    return pd.DataFrame(rows)


def test_feature_contract_rejects_identifier_and_protected_fields():
    row = {column: 1 for column in FEATURE_COLUMNS}
    with pytest.raises(ValueError, match="Identifiers"):
        validate_feature_frame([{**row, "id_student": "learner"}])
    with pytest.raises(ValueError, match="protected"):
        validate_feature_frame([{**row, "gender": "F"}])


def test_grouped_split_keeps_each_learner_in_one_partition():
    groups = [str(value) for value in range(50) for _ in range(2)]
    splits = grouped_train_validation_test_indices(groups, seed=17)
    sets = [{groups[index] for index in split} for split in splits]
    assert not sets[0] & sets[1]
    assert not sets[0] & sets[2]
    assert not sets[1] & sets[2]


def test_training_persists_pipeline_metadata_and_fresh_inference_contract(tmp_path):
    data = _training_rows()
    artifact = tmp_path / "model.joblib"
    result = train_baseline(data, artifact_path=artifact, seed=42)

    assert artifact.is_file()
    assert artifact.with_suffix(".metadata.json").is_file()
    assert artifact.with_suffix(".evaluation.json").is_file()
    metadata = json.loads(artifact.with_suffix(".metadata.json").read_text())
    assert metadata["feature_columns"] == FEATURE_COLUMNS
    assert metadata["group_key"] == "id_student"
    assert metadata["positive_class"] == "Withdrawn"
    assert result["evaluation"]["test"]["roc_auc"] is not None
    assert result["evaluation"]["baseline_test"]["roc_auc"] == 0.5
    assert result["evaluation"]["baseline_test"]["record_count"] == result["metadata"]["split"]["row_counts"]["test"]

    # Independently load the saved pipeline, as a fresh backend process would.
    model, loaded_metadata = load_inference_artifact(artifact)
    assert loaded_metadata["model_version"] == "churnshield-oulad-rf-1.0.0"
    features = data.loc[:1, FEATURE_COLUMNS].copy()
    outputs = predict_records(
        features,
        record_ids=["dataset-learner-a", "dataset-learner-b"],
        artifact_path=artifact,
    )
    repeated_outputs = predict_records(
        features,
        record_ids=["dataset-learner-a", "dataset-learner-b"],
        artifact_path=artifact,
    )
    assert [item["record_id"] for item in outputs] == ["dataset-learner-a", "dataset-learner-b"]
    assert [item["risk_probability"] for item in outputs] == pytest.approx(
        [item["risk_probability"] for item in repeated_outputs], abs=1e-12
    )
    assert all(0 <= item["risk_probability"] <= 1 for item in outputs)
    assert all(item["risk_category"] in {"low", "medium", "high"} for item in outputs)
    assert all(item["model_version"] == metadata["model_version"] for item in outputs)

    inference_input = tmp_path / "fresh_process_input.csv"
    features.to_csv(inference_input, index=False)
    code = (
        "import json,sys,pandas as pd; "
        "from ml.src.inference.predict import predict_records; "
        "result=predict_records(pd.read_csv(sys.argv[1]), record_ids=['fresh-a','fresh-b'], "
        "artifact_path=sys.argv[2]); "
        "print(json.dumps({'count':len(result),'version':result[0]['model_version'], "
        "'valid':all(0 <= item['risk_probability'] <= 1 for item in result)}))"
    )
    fresh = subprocess.run(
        [sys.executable, "-c", code, str(inference_input), str(artifact)],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, check=True,
    )
    fresh_result = json.loads(fresh.stdout)
    assert fresh_result == {"count": 2, "version": metadata["model_version"], "valid": True}


def test_inference_rejects_missing_or_incompatible_features(tmp_path):
    with pytest.raises(InferenceContractError, match="missing or unreadable"):
        load_inference_artifact(tmp_path / "missing.joblib")

    row = {column: 1 for column in FEATURE_COLUMNS if column != CATEGORICAL_FEATURES[0]}
    with pytest.raises(InferenceContractError, match="Missing canonical"):
        predict_records([row], record_ids=["record"], artifact_path=tmp_path / "model.joblib")


def test_probability_metrics_and_risk_category_boundaries():
    result = evaluate_probabilities([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])
    assert result["positive_class"] == "target_withdrawn=1 (Withdrawn)"
    assert result["confusion_matrix"]["rows_actual_columns_predicted"] == [[2, 0], [0, 2]]
    assert result["positive_prevalence"] == 0.5
    assert result["false_negatives"] == 0
    assert result["brier_score"] >= 0
    assert result["log_loss"] >= 0
    assert sum(item["count"] for item in result["calibration_bins_equal_width_0_1"]) == 4
    assert risk_category(0.299) == "low"
    assert risk_category(0.30) == "medium"
    assert risk_category(0.70) == "high"
    with pytest.raises(ValueError):
        risk_category(1.01)


def test_shap_returns_contributions_aligned_to_canonical_features(tmp_path):
    data = _training_rows()
    data.loc[0, NUMERIC_FEATURES[0]] = float("nan")
    artifact = tmp_path / "explainable.joblib"
    train_baseline(data, artifact_path=artifact, seed=42)
    model, _ = load_inference_artifact(artifact)

    result = explain_with_shap(model, data.loc[:0, FEATURE_COLUMNS])
    repeated = explain_with_shap(model, data.loc[:0, FEATURE_COLUMNS])

    assert len(result) == 1
    assert {item["feature_name"] for item in result[0]} == set(FEATURE_COLUMNS)
    assert all(pd.notna(item["contribution"]) for item in result[0])
    assert result == repeated
