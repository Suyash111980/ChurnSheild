from __future__ import annotations

import pandas as pd
import pytest

from ml.src.features.build_features import FEATURE_COLUMNS, NUMERIC_FEATURES, FeatureContractError, validate_feature_frame
from ml.src.inference.batch_predict import predict_csv
from ml.src.inference.predict import InferenceContractError, predict_records
from ml.src.recommendations.recommendation_rules import recommend_for_records
from ml.src.training.train import train_baseline
import ml.src.inference.predict as predictor


def _rows():
    rows = []
    for learner in range(90):
        row = {
            "id_student": str(learner),
            "code_module": "AAA",
            "code_presentation": "2014J",
            "target_withdrawn": learner % 2,
        }
        row.update({name: float(learner % 5 + position) for position, name in enumerate(NUMERIC_FEATURES)})
        row["vle_has_activity_by_cutoff"] = 0 if learner == 0 else 1
        row["assessments_without_submission_recorded_by_cutoff"] = 1 if learner == 1 else 0
        rows.append(row)
    return pd.DataFrame(rows)


def test_batch_predict_writes_stable_contract_and_protects_input(tmp_path):
    data = _rows()
    artifact = tmp_path / "model.joblib"
    train_baseline(data, artifact_path=artifact, seed=42)
    source = tmp_path / "input.csv"
    output = tmp_path / "predictions.csv"
    data.loc[:1, [column for column in data.columns if column != "target_withdrawn"]].to_csv(source, index=False)

    assert predict_csv(source, output, artifact) == 2
    predictions = pd.read_csv(output)
    assert predictions.columns.tolist() == [
        "id_student", "code_module", "code_presentation", "risk_probability",
        "risk_category", "model_version", "predicted_at",
    ]
    assert len(predictions) == 2
    assert predictions.risk_probability.between(0, 1).all()
    assert set(predictions.risk_category).issubset({"low", "medium", "high"})
    with pytest.raises(InferenceContractError, match="already exists"):
        predict_csv(source, output, artifact)
    with pytest.raises(InferenceContractError, match="must not overwrite"):
        predict_csv(source, source, artifact)


def test_batch_predict_rejects_training_target(tmp_path):
    source = tmp_path / "labelled.csv"
    _rows().loc[:0].to_csv(source, index=False)
    with pytest.raises(InferenceContractError, match="target column"):
        predict_csv(source, tmp_path / "out.csv", tmp_path / "missing.joblib")


def test_batch_predict_rejects_missing_and_unexpected_columns(tmp_path):
    data = _rows().drop(columns=[FEATURE_COLUMNS[-1]])
    source = tmp_path / "missing_feature.csv"
    data.loc[:0].drop(columns=["target_withdrawn"]).to_csv(source, index=False)
    with pytest.raises(InferenceContractError, match="missing columns"):
        predict_csv(source, tmp_path / "missing_out.csv", tmp_path / "unused.joblib")

    data = _rows().loc[:0].drop(columns=["target_withdrawn"])
    data["unexpected_feature"] = 7
    data.to_csv(source, index=False)
    with pytest.raises(InferenceContractError, match="unexpected columns"):
        predict_csv(source, tmp_path / "unexpected_out.csv", tmp_path / "unused.joblib")


def test_batch_input_handles_missing_values_and_unknown_categories(tmp_path):
    data = _rows()
    artifact = tmp_path / "model.joblib"
    train_baseline(data, artifact_path=artifact, seed=42)
    row = data.loc[0, FEATURE_COLUMNS].to_dict()
    row["code_module"] = "UNSEEN_MODULE"
    row[NUMERIC_FEATURES[0]] = None
    source = tmp_path / "unknown.csv"
    pd.DataFrame([{"id_student": "0", "code_module": "UNSEEN_MODULE", "code_presentation": "2014J", **{
        name: row[name] for name in FEATURE_COLUMNS if name not in {"code_module", "code_presentation"}
    }}]).to_csv(source, index=False)

    assert predict_csv(source, tmp_path / "result.csv", artifact) == 1
    result = pd.read_csv(tmp_path / "result.csv")
    assert result.risk_probability.between(0, 1).all()

    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(InferenceContractError, match="could not be parsed"):
        predict_csv(empty, tmp_path / "empty_out.csv", artifact)


def test_malformed_numeric_input_and_invalid_model_outputs_fail_closed(monkeypatch):
    row = {column: 1 for column in FEATURE_COLUMNS}
    row[NUMERIC_FEATURES[0]] = "bad numeric"
    with pytest.raises(FeatureContractError, match="malformed"):
        validate_feature_frame([row])

    class InvalidProbabilityModel:
        classes_ = [0, 1]

        def predict_proba(self, values):
            return [[0.9, 0.9] for _ in range(len(values))]

    monkeypatch.setattr(predictor, "load_inference_artifact", lambda path: (InvalidProbabilityModel(), {"model_version": "test"}))
    row[NUMERIC_FEATURES[0]] = 1
    with pytest.raises(InferenceContractError, match="invalid probabilities"):
        predict_records([row], record_ids=["record"], artifact_path="unused")


def test_recommendation_rules_are_evidence_linked_and_human_reviewed():
    row = {column: 1 for column in FEATURE_COLUMNS}
    row.update({"vle_has_activity_by_cutoff": 0, "assessments_without_submission_recorded_by_cutoff": 2})

    suggestions = recommend_for_records([row])[0]

    assert {item["rule_id"] for item in suggestions} == {
        "no_observed_vle_activity_by_cutoff",
        "assessment_without_submission_recorded_by_cutoff",
    }
    assert all(item["requires_human_review"] for item in suggestions)
    assert all("evidence" in item for item in suggestions)
    assert all(set(item) == {"rule_id", "action", "evidence", "requires_human_review"} for item in suggestions)
    assert "not proof" in suggestions[1]["evidence"]["interpretation"]


def test_no_recommendation_when_supported_signals_are_absent():
    row = {column: 1 for column in FEATURE_COLUMNS}
    row.update({"vle_has_activity_by_cutoff": 1, "assessments_without_submission_recorded_by_cutoff": 0})

    assert recommend_for_records([row]) == [[]]


def test_recommendations_are_deterministic_and_missing_evidence_is_not_invented():
    row = {column: 1 for column in FEATURE_COLUMNS}
    row.update({"vle_has_activity_by_cutoff": None, "assessments_without_submission_recorded_by_cutoff": None})
    first = recommend_for_records([row])
    second = recommend_for_records([row])

    assert first == second == [[]]
