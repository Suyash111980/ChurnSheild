"""Train and evaluate a reproducible, learner-grouped Random Forest baseline."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.src.features.build_features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    SCHEMA_VERSION,
    TARGET_COLUMN,
    validate_training_frame,
)
from ml.src.training.evaluate import evaluate_probabilities
from ml.src.training.split_data import grouped_train_validation_test_indices

MODEL_VERSION = "churnshield-oulad-rf-1.0.0"
RANDOM_SEED = 42
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "oulad-learner-v1.json"
FEATURE_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def build_model_pipeline(seed: int = RANDOM_SEED) -> Pipeline:
    """Create the shared preprocessing and estimator pipeline."""
    numeric_pipeline = Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True))])
    categorical_pipeline = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocessor = ColumnTransformer(
        [("numeric", numeric_pipeline, NUMERIC_FEATURES),
         ("categorical", categorical_pipeline, CATEGORICAL_FEATURES)],
        remainder="drop",
        verbose_feature_names_out=True,
    )
    classifier = RandomForestClassifier(
        n_estimators=300,
        max_features="sqrt",
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=seed,
        n_jobs=-1,
    )
    return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def train_baseline(
    dataset: pd.DataFrame,
    *,
    artifact_path: str | Path,
    seed: int = RANDOM_SEED,
    model_version: str = MODEL_VERSION,
) -> dict:
    """Fit only on training learners and persist a verifiable pipeline artifact."""
    features, labels, groups = validate_training_frame(dataset)
    train_idx, validation_idx, test_idx = grouped_train_validation_test_indices(
        groups.to_numpy(), seed=seed
    )
    for name, indices in (("train", train_idx), ("validation", validation_idx), ("test", test_idx)):
        if labels.iloc[indices].nunique() != 2:
            raise ValueError(f"The grouped {name} partition must contain both target classes")

    pipeline = build_model_pipeline(seed)
    pipeline.fit(features.iloc[train_idx], labels.iloc[train_idx])

    validation_probabilities = pipeline.predict_proba(features.iloc[validation_idx])[:, 1]
    test_probabilities = pipeline.predict_proba(features.iloc[test_idx])[:, 1]
    evaluation = {
        "validation": evaluate_probabilities(labels.iloc[validation_idx], validation_probabilities),
        "test": evaluate_probabilities(labels.iloc[test_idx], test_probabilities),
    }
    # A prevalence-only reference makes the Random Forest's held-out scores
    # interpretable; it is fitted on training labels only.
    reference = DummyClassifier(strategy="prior")
    reference.fit(features.iloc[train_idx], labels.iloc[train_idx])
    evaluation["baseline_validation"] = evaluate_probabilities(
        labels.iloc[validation_idx], reference.predict_proba(features.iloc[validation_idx])[:, 1]
    )
    evaluation["baseline_test"] = evaluate_probabilities(
        labels.iloc[test_idx], reference.predict_proba(features.iloc[test_idx])[:, 1]
    )
    # This is a development baseline, not a production-validated model.
    # Do not tune thresholds on the held-out test partition.
    metadata = {
        "model_version": model_version,
        "schema_version": SCHEMA_VERSION,
        "target": TARGET_COLUMN,
        "positive_class": "Withdrawn",
        "target_mapping": FEATURE_SCHEMA["target_mapping"],
        "analysis_unit": "learner-course-presentation row",
        "feature_cutoff_day": 30,
        "feature_cutoff_day_status": "provisional per Phase 2 preparation proposal",
        "group_key": "id_student",
        "feature_columns": FEATURE_COLUMNS,
        "excluded_columns": [
            "id_student", "target_withdrawn", "final_result", "date_unregistration",
            "student_name", "gender", "region", "highest_education", "imd_band",
            "age_band", "disability",
        ],
        "preprocessing": {
            "numeric": "median imputation with missing indicators",
            "categorical": "most-frequent imputation and one-hot encoding; unknowns ignored",
            "fit_scope": "training learners only",
        },
        "model_configuration": {
            "estimator": "RandomForestClassifier",
            "n_estimators": 300,
            "max_features": "sqrt",
            "min_samples_leaf": 2,
            "class_weight": "balanced_subsample",
            "random_seed": seed,
        },
        "split": {
            "method": "GroupShuffleSplit by id_student",
            "approximate_proportions": {"train": 0.60, "validation": 0.20, "test": 0.20},
            "learner_groups": {
                "train": int(groups.iloc[train_idx].nunique()),
                "validation": int(groups.iloc[validation_idx].nunique()),
                "test": int(groups.iloc[test_idx].nunique()),
            },
            "row_counts": {
                "train": int(len(train_idx)),
                "validation": int(len(validation_idx)),
                "test": int(len(test_idx)),
            },
        },
        "risk_bands": FEATURE_SCHEMA["risk_bands"],
        "risk_bands_status": "provisional; requires operational review before deployment",
        "operational_decision_threshold": 0.5,
        "operational_threshold_status": "baseline default; requires validation and approval",
        "probability_calibration_status": "uncalibrated RandomForest predict_proba scores; not calibrated risk probabilities",
        "limitations": [
            "Day-30 cutoff and binary target follow the documented Phase 2 proposal.",
            "Sampled prepared cohort is not a population-representative test set.",
            "Random grouped holdout does not establish temporal or external generalization.",
            "Sensitive and demographic attributes are excluded pending fairness review.",
            "Risk bands are provisional and must not drive high-impact decisions alone.",
        ],
        "prepared_cohort": {
            "rows": int(len(dataset)),
            "unique_learners": int(groups.nunique()),
            "class_counts": {
                "0": int((labels == 0).sum()),
                "1": int((labels == 1).sum()),
            },
            "source_artifact_type": "prepared development sample; not population representative",
        },
    }
    artifact = Path(artifact_path).expanduser().resolve()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{artifact.name}.", suffix=".tmp", dir=artifact.parent)
    os.close(fd)
    try:
        joblib.dump(pipeline, temp_name)
        os.replace(temp_name, artifact)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    _atomic_json(artifact.with_suffix(".metadata.json"), metadata)
    _atomic_json(artifact.with_suffix(".evaluation.json"), evaluation)
    return {"artifact_path": str(artifact), "metadata": metadata, "evaluation": evaluation}


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=root / "ml/data/processed/oulad_learner_features.csv")
    parser.add_argument("--artifact", type=Path, default=root / "ml/artifacts/churn_model.joblib")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args(argv)
    dataset = pd.read_csv(args.data, dtype={"id_student": "string"})
    result = train_baseline(dataset, artifact_path=args.artifact, seed=args.seed)
    print(json.dumps({
        "model_version": result["metadata"]["model_version"],
        "schema_version": result["metadata"]["schema_version"],
        "artifact_path": result["artifact_path"],
        "split": result["metadata"]["split"],
        "test_metrics": result["evaluation"]["test"],
        "test_prevalence_baseline_metrics": result["evaluation"]["baseline_test"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
