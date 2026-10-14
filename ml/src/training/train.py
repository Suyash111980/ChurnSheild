"""Train, evaluate, and version Phase 3 ChurnShield models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier

from ml.src.features.model_schema import (
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, RAW_FEATURES, TARGET_COLUMN,
    validate_feature_frame,
)
from ml.src.training.evaluate import evaluate_binary_model
from ml.src.training.split_data import split_dataset

MODEL_VERSION_PREFIX = "phase3"
DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "processed" / "oulad_learner_features.csv"
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts"


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="__MISSING__")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])
    return ColumnTransformer([
        ("numeric", numeric, list(NUMERIC_FEATURES)),
        ("categorical", categorical, list(CATEGORICAL_FEATURES)),
    ], remainder="drop", verbose_feature_names_out=True)


def _pipeline(estimator) -> Pipeline:
    return Pipeline([("preprocess", _preprocessor()), ("classifier", estimator)])


def _json_ready(value):
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _dump_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(_json_ready(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def train_models(data: pd.DataFrame, artifact_dir: str | Path, *, seed: int = 42,
                 threshold: float = 0.5, n_estimators: int = 300,
                 max_depth: int | None = None, n_jobs: int = -1) -> dict:
    """Fit logistic baseline and Random Forest using train rows only."""
    if TARGET_COLUMN not in data:
        raise ValueError(f"Training data is missing target column {TARGET_COLUMN!r}")
    if set(data[TARGET_COLUMN].dropna().unique()) != {0, 1}:
        raise ValueError("Training data target must include both binary labels 0 and 1")
    features = validate_feature_frame(data)
    labels = data[TARGET_COLUMN].astype(int).reset_index(drop=True)
    features = features.reset_index(drop=True)
    split_source = data.reset_index(drop=True)
    splits = split_dataset(split_source, seed=seed)

    estimators = {
        "baseline_logistic": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed),
        "random_forest": RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth, min_samples_leaf=2,
            class_weight="balanced_subsample", random_state=seed, n_jobs=n_jobs,
        ),
    }
    models = {}
    metrics = {}
    for name, estimator in estimators.items():
        model = _pipeline(estimator)
        train_idx = splits["train"]
        model.fit(features.iloc[train_idx], labels.iloc[train_idx])
        models[name] = model
        metrics[name] = {
            split_name: evaluate_binary_model(model, features.iloc[index], labels.iloc[index], threshold)
            for split_name, index in splits.items()
        }

    rf = models["random_forest"]
    final_names = rf.named_steps["preprocess"].get_feature_names_out().tolist()
    transformed = rf.named_steps["preprocess"].transform(features.iloc[splits["train"]])
    classifier = rf.named_steps["classifier"]
    if transformed.shape[1] != len(final_names) or transformed.shape[1] != classifier.n_features_in_:
        raise RuntimeError("Saved feature schema does not match Random Forest input dimension")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    version = f"{MODEL_VERSION_PREFIX}-{timestamp}"
    output = Path(artifact_dir).expanduser().resolve() / version
    output.mkdir(parents=True, exist_ok=False)
    joblib.dump(rf, output / "random_forest_pipeline.joblib", compress=3)
    joblib.dump(models["baseline_logistic"], output / "baseline_logistic_pipeline.joblib", compress=3)

    split_summary = {}
    groups = split_source["id_student"].to_numpy()
    for split_name, index in splits.items():
        values = labels.iloc[index].value_counts().sort_index()
        split_summary[split_name] = {
            "rows": int(len(index)),
            "unique_students": int(pd.Series(groups[index]).nunique()),
            "class_counts": {str(int(k)): int(v) for k, v in values.items()},
        }

    schema = {
        "model_version": version,
        "input_kind": "Phase 2 prepared learner-course-presentation feature rows",
        "target_column_excluded_from_inputs": TARGET_COLUMN,
        "positive_class": 1,
        "raw_input_features": [
            {"name": col, "type": "categorical" if col in CATEGORICAL_FEATURES else "numeric", "required": True, "nullable": True}
            for col in RAW_FEATURES
        ],
        "optional_non_feature_columns_ignored": ["id_student", "target_withdrawn", "student_name"],
        "model_features_also_returned_as_identifiers": ["code_module", "code_presentation"],
        "display_only_columns_ignored": ["student_name"],
        "categorical_encoding": "OneHotEncoder(handle_unknown='ignore'); missing categories use __MISSING__",
        "numeric_handling": "Median imputation then standard scaling; all-missing training columns retained as zero",
        "final_model_features": final_names,
        "final_model_feature_count": len(final_names),
        "decision_threshold": threshold,
        "prediction_output": {
            "model_version": "string", "predicted_class": "integer (0/1)",
            "withdrawal_risk_probability": "float in [0, 1] for positive class 1",
        },
    }
    evaluation = {
        "model_version": version,
        "positive_class": 1,
        "positive_class_meaning": "Withdrawn",
        "negative_class_meaning": "Pass, Fail, or Distinction",
        "threshold": threshold,
        "classification_metrics": "binary; positive label 1; zero_division=0",
        "roc_auc": "computed from predicted probability for class 1",
        "splits": split_summary,
        "models": metrics,
        "confusion_matrix_axis_order": {"rows": "actual [0, 1]", "columns": "predicted [0, 1]"},
    }
    metadata = {
        "model_version": version,
        "created_utc": timestamp,
        "target": {"column": TARGET_COLUMN, "positive_class": 1, "definition": "Withdrawn=1; Pass/Fail/Distinction=0"},
        "observation_cutoff_day": 30,
        "seed": seed,
        "split_strategy": "nested StratifiedGroupKFold; 5 outer folds for test, then 4 folds of remaining data for validation; groups=id_student",
        "split_counts": split_summary,
        "random_forest": {
            "n_estimators": n_estimators, "max_depth": max_depth, "min_samples_leaf": 2,
            "class_weight": "balanced_subsample", "random_state": seed, "n_jobs": n_jobs,
        },
        "baseline": {"estimator": "LogisticRegression", "max_iter": 1000, "class_weight": "balanced", "random_state": seed},
        "threshold": threshold,
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "artifact_files": ["random_forest_pipeline.joblib", "baseline_logistic_pipeline.joblib", "metadata.json", "evaluation.json", "feature_schema.json", "feature_importance.json"],
        "training_rows": int(len(data)),
        "unique_students": int(data["id_student"].nunique()),
    }
    _dump_json(output / "feature_schema.json", schema)
    _dump_json(output / "evaluation.json", evaluation)
    importances = sorted(
        ({"feature": name, "importance": float(value)} for name, value in zip(final_names, classifier.feature_importances_)),
        key=lambda row: row["importance"], reverse=True,
    )
    _dump_json(output / "feature_importance.json", {
        "model_version": version,
        "note": "Random Forest impurity-based importance describes model use, not causality.",
        "features": importances,
    })
    _dump_json(output / "metadata.json", metadata)
    return {"model_version": version, "artifact_dir": output, "schema": schema,
            "evaluation": evaluation, "metadata": metadata}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Phase 2 prepared feature CSV")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--n-jobs", type=int, default=-1)
    args = parser.parse_args(argv)
    if not args.data.is_file():
        parser.error(f"Prepared feature CSV does not exist: {args.data}. Run ml.src.prepare_oulad first.")
    data = pd.read_csv(args.data)
    result = train_models(data, args.artifact_dir, seed=args.seed, threshold=args.threshold,
                          n_estimators=args.n_estimators, max_depth=args.max_depth, n_jobs=args.n_jobs)
    print(f"Model version: {result['model_version']}")
    print(f"Artifacts: {result['artifact_dir']}")
    print(json.dumps(result["evaluation"]["models"]["random_forest"]["test"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
