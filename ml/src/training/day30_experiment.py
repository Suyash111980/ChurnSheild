"""Train a separate Day-30-active OULAD experiment with temporal holdout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

from ml.src.features.build_features import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
    SCHEMA_VERSION,
    TARGET_COLUMN,
    validate_training_frame,
)
from ml.src.training.evaluate import evaluate_probabilities
from ml.src.training.split_data import grouped_train_validation_test_indices
from ml.src.training.train import build_model_pipeline


DAY30_MODEL_VERSION = "churnshield-oulad-day30-temporal-1.0.0"


def build_day30_cohort(
    features: pd.DataFrame,
    registration: pd.DataFrame,
    *,
    cutoff_day: float = 30.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Keep rows known to be registered and not withdrawn at the score date.

    Withdrawn outcomes with no recorded unregistration date are excluded because
    their timing relative to the prediction cutoff cannot be established.
    """
    if cutoff_day < 0:
        raise ValueError("cutoff_day must be non-negative")
    keys = IDENTIFIER_COLUMNS
    required = keys + ["date_registration", "date_unregistration"]
    missing = [column for column in required if column not in registration.columns]
    if missing:
        raise ValueError(f"Registration data is missing required column(s): {', '.join(missing)}")
    validate_training_frame(features)
    if registration.duplicated(keys).any():
        raise ValueError("Registration rows must be unique by learner, module, and presentation")
    dates = registration[keys + ["date_registration", "date_unregistration"]].copy()
    for column in ("date_registration", "date_unregistration"):
        dates[column] = pd.to_numeric(dates[column], errors="coerce")
    if (registration["date_registration"].notna() & dates["date_registration"].isna()).any():
        raise ValueError("date_registration must be numeric or missing")
    if (registration["date_unregistration"].notna() & dates["date_unregistration"].isna()).any():
        raise ValueError("date_unregistration must be numeric or missing")

    joined = features.merge(dates, on=keys, how="left", validate="one_to_one", indicator="_registration_match")
    has_registration = joined["_registration_match"].eq("both")
    registered_by_cutoff = has_registration & joined["date_registration"].notna() & joined["date_registration"].le(cutoff_day)
    not_withdrawn_by_cutoff = joined["date_unregistration"].isna() | joined["date_unregistration"].gt(cutoff_day)
    has_timed_positive_label = joined[TARGET_COLUMN].eq(0) | joined["date_unregistration"].gt(cutoff_day)
    eligible = registered_by_cutoff & not_withdrawn_by_cutoff & has_timed_positive_label

    report = {
        "cutoff_day_inclusive": float(cutoff_day),
        "input_rows": int(len(features)),
        "eligible_rows": int(eligible.sum()),
        "excluded_missing_registration_record": int((~has_registration).sum()),
        "excluded_missing_or_after_cutoff_registration_date": int((has_registration & ~registered_by_cutoff).sum()),
        "excluded_unregistered_on_or_before_cutoff": int((registered_by_cutoff & ~not_withdrawn_by_cutoff).sum()),
        "excluded_withdrawn_target_without_timed_unregistration": int(
            (registered_by_cutoff & not_withdrawn_by_cutoff & joined[TARGET_COLUMN].eq(1) & ~has_timed_positive_label).sum()
        ),
        "eligible_target_counts": {
            str(int(label)): int(count)
            for label, count in joined.loc[eligible, TARGET_COLUMN].value_counts().sort_index().items()
        },
        "eligibility_definition": [
            "a registration record exists",
            "date_registration <= cutoff_day",
            "date_unregistration is missing or > cutoff_day",
            "for Withdrawn target rows, date_unregistration must be present and > cutoff_day",
        ],
        "date_unregistration_is_not_a_model_feature": True,
    }
    result = joined.loc[eligible, features.columns].copy().reset_index(drop=True)
    if result.empty or result[TARGET_COLUMN].nunique() != 2:
        raise ValueError("Day-30 eligible cohort must contain both target classes")
    return result, report


def temporal_grouped_indices(
    dataset: pd.DataFrame,
    *,
    train_presentations: tuple[str, ...] = ("2013B", "2013J"),
    validation_presentation: str = "2014B",
    test_presentation: str = "2014J",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Hold out later presentations and remove learner IDs crossing partitions."""
    presentation = dataset["code_presentation"].astype("string")
    train_candidates = np.flatnonzero(presentation.isin(train_presentations).to_numpy())
    validation_candidates = np.flatnonzero(presentation.eq(validation_presentation).to_numpy())
    test = np.flatnonzero(presentation.eq(test_presentation).to_numpy())
    if not len(train_candidates) or not len(validation_candidates) or not len(test):
        raise ValueError("Temporal split requires rows in train, validation, and test presentations")
    groups = dataset["id_student"].astype("string").to_numpy()
    test_groups = set(groups[test])
    validation = np.asarray([i for i in validation_candidates if groups[i] not in test_groups], dtype=int)
    validation_groups = set(groups[validation])
    train = np.asarray([
        i for i in train_candidates
        if groups[i] not in test_groups and groups[i] not in validation_groups
    ], dtype=int)
    if not len(train) or not len(validation) or not len(test):
        raise ValueError("Temporal split is empty after excluding learner overlap")
    if any(dataset.iloc[index][TARGET_COLUMN].nunique() != 2 for index in (train, validation, test)):
        raise ValueError("Each temporal split must contain both withdrawal target classes")
    split_groups = [set(groups[index]) for index in (train, validation, test)]
    if any(split_groups[i] & split_groups[j] for i in range(3) for j in range(i + 1, 3)):
        raise RuntimeError("Learner leakage detected across temporal splits")
    module_sets = [set(dataset.iloc[index]["code_module"].astype("string")) for index in (train, validation, test)]
    presentation_sets = [set(dataset.iloc[index]["code_presentation"].astype("string")) for index in (train, validation, test)]
    report = {
        "method": "forward presentation holdout; disjoint learner groups",
        "train_presentations": list(train_presentations),
        "validation_presentation": validation_presentation,
        "test_presentation": test_presentation,
        "rows": {"train": int(len(train)), "validation": int(len(validation)), "test": int(len(test))},
        "learners": {
            "train": int(len(split_groups[0])),
            "validation": int(len(split_groups[1])),
            "test": int(len(split_groups[2])),
        },
        "removed_train_rows_for_learner_overlap": int(len(train_candidates) - len(train)),
        "removed_validation_rows_for_test_learner_overlap": int(len(validation_candidates) - len(validation)),
        "learner_groups_disjoint": True,
        "presentation_sets": [sorted(values) for values in presentation_sets],
        "presentation_sets_disjoint": not any(
            presentation_sets[i] & presentation_sets[j] for i in range(3) for j in range(i + 1, 3)
        ),
        "train_test_course_modules_overlap": sorted(module_sets[0] & module_sets[2]),
        "train_test_course_module_overlap_count": len(module_sets[0] & module_sets[2]),
    }
    return train, validation, test, report


def run_day30_experiment(
    dataset: pd.DataFrame,
    *,
    seed: int = 42,
    train_presentations: tuple[str, ...] = ("2013B", "2013J"),
    validation_presentation: str = "2014B",
    test_presentation: str = "2014J",
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Fit on earlier presentations and evaluate once on the later test set."""
    features, labels, _ = validate_training_frame(dataset)
    train, validation, test, split_report = temporal_grouped_indices(
        dataset,
        train_presentations=train_presentations,
        validation_presentation=validation_presentation,
        test_presentation=test_presentation,
    )
    model = build_model_pipeline(seed)
    model.fit(features.iloc[train], labels.iloc[train])
    validation_probabilities = model.predict_proba(features.iloc[validation])[:, list(model.classes_).index(1)]
    test_probabilities = model.predict_proba(features.iloc[test])[:, list(model.classes_).index(1)]

    prevalence = DummyClassifier(strategy="prior").fit(features.iloc[train], labels.iloc[train])
    baseline_validation = prevalence.predict_proba(features.iloc[validation])[:, list(prevalence.classes_).index(1)]
    baseline_test = prevalence.predict_proba(features.iloc[test])[:, list(prevalence.classes_).index(1)]
    evaluation = {
        "validation_threshold_0_50": evaluate_probabilities(labels.iloc[validation], validation_probabilities, threshold=0.5),
        "test_threshold_0_50": evaluate_probabilities(labels.iloc[test], test_probabilities, threshold=0.5),
        "prevalence_baseline_validation": evaluate_probabilities(labels.iloc[validation], baseline_validation, threshold=0.5),
        "prevalence_baseline_test": evaluate_probabilities(labels.iloc[test], baseline_test, threshold=0.5),
        "validation_threshold_sensitivity": {
            str(threshold): evaluate_probabilities(labels.iloc[validation], validation_probabilities, threshold=threshold)
            for threshold in (0.3, 0.5, 0.7)
        },
    }
    random_train, random_validation, random_test = grouped_train_validation_test_indices(
        dataset["id_student"].astype("string").to_numpy(), seed=seed
    )
    random_model = build_model_pipeline(seed)
    random_model.fit(features.iloc[random_train], labels.iloc[random_train])
    random_test_probabilities = random_model.predict_proba(features.iloc[random_test])[:, list(random_model.classes_).index(1)]
    random_prevalence = DummyClassifier(strategy="prior").fit(
        features.iloc[random_train], labels.iloc[random_train]
    )
    random_baseline_probabilities = random_prevalence.predict_proba(features.iloc[random_test])[:, list(random_prevalence.classes_).index(1)]
    evaluation["random_grouped_test_same_cohort"] = evaluate_probabilities(
        labels.iloc[random_test], random_test_probabilities, threshold=0.5
    )
    evaluation["random_grouped_prevalence_baseline_test"] = evaluate_probabilities(
        labels.iloc[random_test], random_baseline_probabilities, threshold=0.5
    )
    metadata_random_split = {
        "method": "GroupShuffleSplit by id_student; diagnostic only",
        "seed": seed,
        "rows": {"train": int(len(random_train)), "validation": int(len(random_validation)), "test": int(len(random_test))},
        "learners": {
            "train": int(dataset.iloc[random_train]["id_student"].nunique()),
            "validation": int(dataset.iloc[random_validation]["id_student"].nunique()),
            "test": int(dataset.iloc[random_test]["id_student"].nunique()),
        },
    }
    metadata = {
        "model_version": DAY30_MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "target": "final_result == Withdrawn, with withdrawal date after day 30",
        "positive_class": "Withdrawn after prediction cutoff",
        "analysis_unit": "learner-course-presentation row active at day 30",
        "feature_cutoff_day": 30,
        "feature_columns": FEATURE_COLUMNS,
        "excluded_columns": ["id_student", TARGET_COLUMN, "date_registration", "date_unregistration", "final_result"],
        "random_seed": seed,
        "temporal_split": split_report,
        "random_grouped_split_diagnostic": metadata_random_split,
        "cohort_rows": int(len(dataset)),
        "cohort_class_counts": {str(int(label)): int(count) for label, count in labels.value_counts().sort_index().items()},
        "risk_bands": {"low_max_exclusive": 0.3, "high_min_inclusive": 0.7},
        "risk_bands_status": "provisional; probabilities have not been calibrated",
        "decision_threshold": 0.5,
        "decision_threshold_status": "provisional; no operational cost matrix was supplied",
        "probability_calibration_status": "uncalibrated RandomForest predict_proba scores; not calibrated risk probabilities",
        "limitations": [
            "One development sample and one later presentation are not external validation.",
            "The target, day-30 cutoff, and date_unregistration semantics require domain-owner confirmation.",
            "Day-30 records without a registration row or with an untimed Withdrawn label are excluded.",
            "Temporal grouping uses only four observed presentations in the prepared sample.",
        ],
    }
    return model, metadata, evaluation


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_experiment(model, metadata: dict[str, Any], evaluation: dict[str, Any], artifact_path: str | Path, report_path: str | Path) -> None:
    """Persist a new candidate and aggregate report; never overwrite outputs."""
    artifact = Path(artifact_path).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    sidecars = [artifact, artifact.with_suffix(".metadata.json"), artifact.with_suffix(".evaluation.json"), report]
    existing = [str(path) for path in sidecars if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing experiment output(s): " + ", ".join(existing))
    artifact.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{artifact.name}.", suffix=".tmp", dir=artifact.parent)
    os.close(fd)
    try:
        joblib.dump(model, temporary)
        os.replace(temporary, artifact)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    _write_json(artifact.with_suffix(".metadata.json"), metadata)
    _write_json(artifact.with_suffix(".evaluation.json"), evaluation)
    _write_json(report, {"metadata": metadata, "evaluation": evaluation})


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, default=root / "ml/data/processed/oulad_learner_features.csv")
    parser.add_argument("--registration", type=Path, default=root / "ml/data/raw/studentRegistration.csv")
    parser.add_argument("--artifact", type=Path, default=root / "ml/artifacts/churn_model_day30_candidate.joblib")
    parser.add_argument("--report", type=Path, default=root / "ml/reports/day30_experiment_evaluation.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        features = pd.read_csv(args.features, dtype={IDENTIFIER_COLUMNS[0]: "string"})
        registration = pd.read_csv(args.registration, dtype={IDENTIFIER_COLUMNS[0]: "string"})
        cohort, cohort_report = build_day30_cohort(features, registration)
        model, metadata, evaluation = run_day30_experiment(cohort, seed=args.seed)
        metadata["cohort_filter_report"] = cohort_report
        _, early_metadata, early_evaluation = run_day30_experiment(
            cohort,
            seed=args.seed,
            train_presentations=("2013B",),
            validation_presentation="2013J",
            test_presentation="2014B",
        )
        metadata["earlier_forward_fold"] = early_metadata["temporal_split"]
        evaluation["earlier_forward_fold_validation"] = early_evaluation["validation_threshold_0_50"]
        evaluation["earlier_forward_fold_test"] = early_evaluation["test_threshold_0_50"]
        evaluation["earlier_forward_fold_prevalence_baseline_test"] = early_evaluation["prevalence_baseline_test"]
        save_experiment(model, metadata, evaluation, args.artifact, args.report)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps({
        "model_version": metadata["model_version"],
        "cohort": cohort_report,
        "temporal_split": metadata["temporal_split"],
        "test_metrics": evaluation["test_threshold_0_50"],
        "test_prevalence_baseline": evaluation["prevalence_baseline_test"],
        "artifact": str(args.artifact.expanduser().resolve()),
        "report": str(args.report.expanduser().resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
