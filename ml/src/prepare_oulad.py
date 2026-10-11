"""Build a cutoff-safe, learner-course-presentation OULAD feature table."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


FILES = (
    "studentInfo.csv", "studentAssessment.csv", "assessments.csv",
    "studentVle.csv", "studentRegistration.csv", "courses.csv", "vle.csv",
)
BASE_KEYS = ["id_student", "code_module", "code_presentation"]
COURSE_KEYS = ["code_module", "code_presentation"]
RESOURCE_KEYS = ["id_site", "code_module", "code_presentation"]
TARGET_MAP = {"Withdrawn": 1, "Pass": 0, "Fail": 0, "Distinction": 0}
CONTEXT_FIELDS = (
    "gender", "region", "highest_education", "imd_band", "age_band",
    "num_of_prev_attempts", "studied_credits", "disability",
)

REQUIRED_COLUMNS = {
    "studentInfo.csv": BASE_KEYS + ["final_result"],
    "studentAssessment.csv": ["id_student", "id_assessment", "date_submitted", "is_banked", "score"],
    "assessments.csv": ["id_assessment", "code_module", "code_presentation", "date", "assessment_type", "weight"],
    "studentVle.csv": ["id_student", "code_module", "code_presentation", "id_site", "date", "sum_click"],
    "studentRegistration.csv": BASE_KEYS + ["date_registration", "date_unregistration"],
    "courses.csv": COURSE_KEYS + ["module_presentation_length"],
    "vle.csv": RESOURCE_KEYS + ["activity_type"],
}
NUMERIC_COLUMNS = {
    "studentAssessment.csv": ["id_student", "id_assessment", "date_submitted", "is_banked", "score"],
    "assessments.csv": ["id_assessment", "date", "weight"],
    "studentVle.csv": ["id_student", "id_site", "date", "sum_click"],
    "studentRegistration.csv": ["id_student", "date_registration", "date_unregistration"],
    "courses.csv": ["module_presentation_length"],
    "vle.csv": ["id_site"],
    "studentInfo.csv": ["id_student", "num_of_prev_attempts", "studied_credits"],
}
KEY_COLUMNS = {
    "studentInfo.csv": BASE_KEYS,
    "studentAssessment.csv": ["id_student", "id_assessment"],
    "assessments.csv": ["id_assessment"],
    "studentVle.csv": BASE_KEYS + ["id_site", "date"],
    "studentRegistration.csv": BASE_KEYS,
    "courses.csv": COURSE_KEYS,
    "vle.csv": RESOURCE_KEYS,
}


class DataValidationError(ValueError):
    """Raised when OULAD input cannot be joined or interpreted safely."""


@dataclass
class PreparationResult:
    dataset: pd.DataFrame
    report: dict[str, Any]
    feature_dictionary: pd.DataFrame


def load_oulad_tables(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load all required CSVs without copying or modifying the source files."""
    directory = Path(data_dir).expanduser().resolve()
    missing = [name for name in FILES if not (directory / name).is_file()]
    if missing:
        listing = "\n".join(f"  - {name}" for name in missing)
        raise FileNotFoundError(
            f"Missing required OULAD file(s) in {directory}:\n{listing}\n"
            "Place all seven files in this directory or pass --data-dir with their location."
        )
    tables: dict[str, pd.DataFrame] = {}
    for name in FILES:
        try:
            tables[name] = pd.read_csv(directory / name, low_memory=False)
        except Exception as exc:
            raise DataValidationError(f"Could not read {name} from {directory}: {exc}") from exc
    return tables


def _require_key_values(frame: pd.DataFrame, table: str, columns: list[str]) -> None:
    null_columns = [col for col in columns if frame[col].isna().any()]
    blank_columns = [
        col for col in columns
        if pd.api.types.is_string_dtype(frame[col].dtype)
        and frame[col].astype("string").str.strip().eq("").any()
    ]
    invalid = sorted(set(null_columns + blank_columns))
    if invalid:
        raise DataValidationError(f"{table} has missing or blank values in key column(s): {', '.join(invalid)}")


def _coerce_numeric_columns(tables: dict[str, pd.DataFrame]) -> None:
    for name, columns in NUMERIC_COLUMNS.items():
        frame = tables[name]
        for column in columns:
            original = frame[column]
            converted = pd.to_numeric(original, errors="coerce")
            invalid = original.notna() & converted.isna()
            if invalid.any():
                raise DataValidationError(f"{name}.{column} must contain numeric values (or documented missing values)")
            if column not in {"date", "date_registration", "date_unregistration", "score"} and converted.isna().any():
                raise DataValidationError(f"{name}.{column} contains missing values but is required")
            if not np.isfinite(converted.dropna().to_numpy(dtype=float)).all():
                raise DataValidationError(f"{name}.{column} contains non-finite numeric values")
            frame[column] = converted


def validate_input_tables(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Validate schemas, basic types, required rows, and unique dimension keys."""
    missing_tables = [name for name in FILES if name not in tables]
    if missing_tables:
        raise DataValidationError(f"Input tables are missing: {', '.join(missing_tables)}")
    for name in FILES:
        frame = tables[name]
        if frame.empty:
            raise DataValidationError(f"{name} is empty; expected the required OULAD table to contain rows")
        missing_columns = [col for col in REQUIRED_COLUMNS[name] if col not in frame.columns]
        if missing_columns:
            raise DataValidationError(f"{name} is missing required column(s): {', '.join(missing_columns)}")
        _require_key_values(frame, name, KEY_COLUMNS[name])
    _coerce_numeric_columns(tables)

    for name, key in KEY_COLUMNS.items():
        duplicates = int(tables[name].duplicated(key).sum())
        # studentVle contains exact and repeated event keys in the supplied OULAD export.
        # Exact copies are removed in the selected learner sample; same-key rows with
        # different click values are retained and summed as separate source records.
        if name != "studentVle.csv" and duplicates:
            raise DataValidationError(
                f"{name} has {duplicates:,} duplicate row(s) for expected key {', '.join(key)}; "
                "resolve the key conflict instead of silently dropping records."
            )

    course_keys = tables["courses.csv"][COURSE_KEYS].drop_duplicates()
    for name in ("assessments.csv", "vle.csv"):
        related = tables[name][COURSE_KEYS].drop_duplicates()
        checked = related.merge(course_keys.assign(_course=1), on=COURSE_KEYS, how="left", validate="one_to_one")
        unmatched = int(checked["_course"].isna().sum())
        if unmatched:
            raise DataValidationError(f"{name} contains {unmatched:,} module/presentation key(s) absent from courses.csv")

    bad_clicks = tables["studentVle.csv"]["sum_click"] < 0
    if bad_clicks.any():
        raise DataValidationError("studentVle.csv.sum_click contains negative values")
    score = tables["studentAssessment.csv"]["score"]
    if ((score < 0) | (score > 100)).fillna(False).any():
        raise DataValidationError("studentAssessment.csv.score must be between 0 and 100 when present")
    if not tables["studentAssessment.csv"]["is_banked"].isin([0, 1]).all():
        raise DataValidationError("studentAssessment.csv.is_banked must contain only 0 or 1")
    if (tables["courses.csv"]["module_presentation_length"] <= 0).any():
        raise DataValidationError("courses.csv.module_presentation_length must be positive")
    return {name: len(tables[name]) for name in FILES}


def _assert_unique(frame: pd.DataFrame, keys: list[str], description: str) -> None:
    duplicate_count = int(frame.duplicated(keys).sum())
    if duplicate_count:
        raise DataValidationError(f"{description} contains {duplicate_count:,} duplicate key row(s) for {', '.join(keys)}")


def _merge_one_to_one(left: pd.DataFrame, right: pd.DataFrame, name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    _assert_unique(left, BASE_KEYS, "Current feature table")
    _assert_unique(right, BASE_KEYS, f"{name} aggregate")
    before = len(left)
    merged = left.merge(right, on=BASE_KEYS, how="left", validate="one_to_one", indicator="_merge_status")
    unmatched = int(merged["_merge_status"].eq("left_only").sum())
    merged = merged.drop(columns="_merge_status")
    if len(merged) != before:
        raise DataValidationError(f"{name} merge changed row count from {before:,} to {len(merged):,}")
    return merged, {"feature_table": name, "rows_before": before, "rows_after": len(merged), "unmatched_base_rows": unmatched}


def build_base_table(student_info: pd.DataFrame, courses: pd.DataFrame) -> pd.DataFrame:
    """Construct a unique base with available context and course length."""
    _assert_unique(student_info, BASE_KEYS, "studentInfo base")
    _assert_unique(courses, COURSE_KEYS, "courses table")
    context = [col for col in CONTEXT_FIELDS if col in student_info.columns]
    columns = BASE_KEYS + context + ["final_result"]
    base = student_info[columns].copy()
    before = len(base)
    base = base.merge(courses[COURSE_KEYS + ["module_presentation_length"]], on=COURSE_KEYS,
                      how="left", validate="many_to_one", indicator="_course_status")
    unmatched = int(base["_course_status"].eq("left_only").sum())
    if unmatched:
        raise DataValidationError(f"{unmatched:,} base record(s) do not match courses.csv on code_module/code_presentation")
    base = base.drop(columns="_course_status")
    if len(base) != before:
        raise DataValidationError("Course metadata join unexpectedly changed the base row count")
    return base


def build_registration_features(base: pd.DataFrame, registration: pd.DataFrame, cutoff_day: float) -> tuple[pd.DataFrame, dict[str, int]]:
    """Use registration timing available by cutoff; never expose unregistration."""
    reg = registration[BASE_KEYS + ["date_registration"]]
    _assert_unique(reg, BASE_KEYS, "studentRegistration table")
    features = base[BASE_KEYS].merge(reg, on=BASE_KEYS, how="left", validate="one_to_one", indicator="_registration_status")
    record_present = features["_registration_status"].eq("both")
    date = features["date_registration"]
    by_cutoff = date.notna() & date.le(cutoff_day)
    features["registration_record_present"] = record_present.astype("int8")
    features["registration_by_cutoff"] = by_cutoff.astype("int8")
    features["registration_day_at_cutoff"] = date.where(by_cutoff)
    features["registration_date_missing"] = date.isna().astype("int8")
    unmatched = int((~record_present).sum())
    registration_membership = registration[BASE_KEYS].merge(
        base[BASE_KEYS].drop_duplicates().assign(_base_present=1),
        on=BASE_KEYS, how="left", validate="one_to_one")
    registration_rows_without_base = int(registration_membership["_base_present"].isna().sum())
    features = features.drop(columns=["date_registration", "_registration_status"])
    return features, {
        "base_records_without_registration_row": unmatched,
        "registration_rows_without_base_record": registration_rows_without_base,
    }


def _map_assessment_events(
    submissions: pd.DataFrame, assessments: pd.DataFrame, base_keys: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    assessment_meta = assessments[["id_assessment", "code_module", "code_presentation", "date"]]
    _assert_unique(assessment_meta, ["id_assessment"], "assessments table")
    mapped = submissions.merge(assessment_meta, on="id_assessment", how="left", validate="many_to_one", indicator="_assessment_status")
    unmatched_metadata = int(mapped["_assessment_status"].eq("left_only").sum())
    if unmatched_metadata:
        raise DataValidationError(f"{unmatched_metadata:,} studentAssessment row(s) reference unknown id_assessment values")
    mapped = mapped.drop(columns="_assessment_status")
    linked = mapped.merge(base_keys[BASE_KEYS].drop_duplicates().assign(_base_present=1),
                          on=BASE_KEYS, how="left", validate="many_to_one")
    unmatched_base = linked["_base_present"].isna()
    metrics = {
        "assessment_rows_without_metadata": unmatched_metadata,
        "assessment_rows_without_base_record": int(unmatched_base.sum()),
        "distinct_assessment_base_keys_without_base_record": int(linked.loc[unmatched_base, BASE_KEYS].drop_duplicates().shape[0]),
    }
    linked = linked.loc[~unmatched_base].drop(columns="_base_present")
    return linked, metrics


def build_assessment_features(
    base: pd.DataFrame, assessments: pd.DataFrame, submissions: pd.DataFrame,
    cutoff_day: float, all_base_keys: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Aggregate due/submission behavior; scores are excluded without release timing."""
    keys_all = all_base_keys if all_base_keys is not None else base
    mapped, metrics = _map_assessment_events(submissions, assessments, keys_all)
    due_meta = assessments.loc[assessments["date"].notna() & assessments["date"].le(cutoff_day),
                               ["id_assessment", "code_module", "code_presentation", "date"]]
    due_by_course = due_meta.groupby(COURSE_KEYS, as_index=False).size().rename(columns={"size": "assessments_due_by_cutoff"})
    features = base[BASE_KEYS].merge(due_by_course, on=COURSE_KEYS, how="left", validate="many_to_one")
    features["assessments_due_by_cutoff"] = features["assessments_due_by_cutoff"].fillna(0).astype("int64")

    selected_keys = base[BASE_KEYS].drop_duplicates()
    mapped = mapped.merge(selected_keys.assign(_selected=1), on=BASE_KEYS, how="inner", validate="many_to_one")
    observed = mapped.loc[mapped["date_submitted"].le(cutoff_day)].copy()
    banked = observed.loc[observed["is_banked"].eq(1)]
    current_observed = observed.loc[observed["is_banked"].eq(0)]
    banked_by_key = banked.groupby(BASE_KEYS, as_index=False).agg(
        assessment_banked_results_by_cutoff=("id_assessment", "nunique"))
    submissions_by_key = current_observed.groupby(BASE_KEYS, as_index=False).agg(
        assessment_submissions_by_cutoff=("id_assessment", "nunique"))
    # Late counts are calculated separately because due dates are event-specific.
    late = current_observed.loc[current_observed["date"].notna() & current_observed["date_submitted"].gt(current_observed["date"])]
    late_counts = late.groupby(BASE_KEYS, as_index=False).size().rename(columns={"size": "assessment_late_submissions_by_cutoff"})
    submissions_by_key = submissions_by_key.merge(late_counts, on=BASE_KEYS, how="left", validate="one_to_one")
    submissions_by_key["assessment_late_submissions_by_cutoff"] = submissions_by_key["assessment_late_submissions_by_cutoff"].fillna(0).astype("int64")
    features = features.merge(submissions_by_key, on=BASE_KEYS, how="left", validate="one_to_one")

    # A record is "without submission recorded" only when its assessment is due
    # by the cutoff and no associated submission was observed by the cutoff.
    due_pairs = base[BASE_KEYS].merge(due_meta[["id_assessment", "code_module", "code_presentation"]],
                                     on=COURSE_KEYS, how="inner", validate="many_to_many")
    submitted_due = current_observed.loc[current_observed["id_assessment"].isin(due_meta["id_assessment"]), BASE_KEYS + ["id_assessment"]].drop_duplicates()
    banked_due = banked.loc[banked["id_assessment"].isin(due_meta["id_assessment"]), BASE_KEYS + ["id_assessment"]].drop_duplicates()
    due_pairs = due_pairs.merge(submitted_due.assign(_submitted=1), on=BASE_KEYS + ["id_assessment"],
                                how="left", validate="one_to_one")
    due_pairs = due_pairs.merge(banked_due.assign(_banked=1), on=BASE_KEYS + ["id_assessment"],
                                how="left", validate="one_to_one")
    missing_due = due_pairs.loc[due_pairs["_submitted"].isna() & due_pairs["_banked"].isna()].groupby(BASE_KEYS, as_index=False).size()
    missing_due = missing_due.rename(columns={"size": "assessments_without_submission_recorded_by_cutoff"})
    features = features.merge(missing_due, on=BASE_KEYS, how="left", validate="one_to_one")
    features = features.merge(banked_by_key, on=BASE_KEYS, how="left", validate="one_to_one")
    for column in ("assessment_submissions_by_cutoff", "assessment_late_submissions_by_cutoff",
                   "assessments_without_submission_recorded_by_cutoff", "assessment_banked_results_by_cutoff"):
        features[column] = features[column].fillna(0).astype("int64")
    banked_due_counts = due_pairs.loc[due_pairs["_banked"].notna()].groupby(BASE_KEYS, as_index=False).size()
    banked_due_counts = banked_due_counts.rename(columns={"size": "_banked_due_count"})
    features = features.merge(banked_due_counts, on=BASE_KEYS, how="left", validate="one_to_one")
    features["_banked_due_count"] = features["_banked_due_count"].fillna(0)
    denominator = features["assessments_due_by_cutoff"] - features["_banked_due_count"]
    features["assessment_submission_rate_by_cutoff"] = np.where(
        denominator.gt(0),
        (denominator - (features["assessments_without_submission_recorded_by_cutoff"])) / denominator,
        np.nan,
    )
    features = features.drop(columns="_banked_due_count")
    if len(features) != len(base) or features.duplicated(BASE_KEYS).any():
        raise DataValidationError("Assessment feature aggregation changed row cardinality")
    metrics.update({
        "assessment_metadata_rows_due_by_cutoff": len(due_meta),
        "assessment_submission_rows_by_cutoff_in_sample": len(observed),
        "banked_assessment_rows_by_cutoff_in_sample": len(banked),
    })
    return features, metrics


def build_vle_features(
    base: pd.DataFrame, student_vle: pd.DataFrame, vle_metadata: pd.DataFrame,
    cutoff_day: float, all_base_keys: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Aggregate VLE events through the inclusive cutoff for the selected base rows."""
    metadata = vle_metadata[RESOURCE_KEYS].copy()
    _assert_unique(metadata, RESOURCE_KEYS, "vle resource metadata")
    selected_learners = base["id_student"].drop_duplicates()
    sample_events = student_vle.loc[student_vle["id_student"].isin(selected_learners)].copy()
    selected_keys = base[BASE_KEYS].drop_duplicates()
    sample_events = sample_events.merge(selected_keys.assign(_selected=1), on=BASE_KEYS, how="left", validate="many_to_one")
    unmatched_base = sample_events["_selected"].isna()
    unmatched_event_keys = int(sample_events.loc[unmatched_base, BASE_KEYS].drop_duplicates().shape[0])
    sample_events = sample_events.loc[~unmatched_base].drop(columns="_selected")

    resource_keys = sample_events[RESOURCE_KEYS].drop_duplicates()
    resource_check = resource_keys.merge(metadata.assign(_resource=1), on=RESOURCE_KEYS, how="left", validate="one_to_one")
    unmatched_resources = int(resource_check["_resource"].isna().sum())
    if unmatched_resources:
        raise DataValidationError(f"{unmatched_resources:,} sampled VLE resource keys do not match vle.csv on id_site/module/presentation")

    raw_sample_event_rows = len(sample_events)
    exact_duplicates = int(sample_events.duplicated().sum())
    sample_events = sample_events.drop_duplicates()
    eligible = sample_events.loc[sample_events["date"].le(cutoff_day)].copy()
    eligible["_clicks_day_0_7"] = eligible["sum_click"].where(eligible["date"].between(0, 7), 0)
    eligible["_clicks_day_8_cutoff"] = eligible["sum_click"].where(eligible["date"].between(8, cutoff_day), 0)
    grouped = eligible.groupby(BASE_KEYS, as_index=False).agg(
        vle_total_clicks_by_cutoff=("sum_click", "sum"),
        vle_active_days_by_cutoff=("date", "nunique"),
        vle_distinct_resources_by_cutoff=("id_site", "nunique"),
        vle_last_activity_day_by_cutoff=("date", "max"),
        vle_clicks_day_0_7=("_clicks_day_0_7", "sum"),
        vle_clicks_day_8_cutoff=("_clicks_day_8_cutoff", "sum"),
    )
    features = base[BASE_KEYS].merge(grouped, on=BASE_KEYS, how="left", validate="one_to_one")
    count_features = ["vle_total_clicks_by_cutoff", "vle_active_days_by_cutoff",
                      "vle_distinct_resources_by_cutoff", "vle_clicks_day_0_7", "vle_clicks_day_8_cutoff"]
    features["vle_has_activity_by_cutoff"] = features["vle_last_activity_day_by_cutoff"].notna().astype("int8")
    for column in count_features:
        features[column] = features[column].fillna(0).astype("int64")
    features["vle_days_since_last_activity_at_cutoff"] = cutoff_day - features["vle_last_activity_day_by_cutoff"]
    features = features.drop(columns="vle_last_activity_day_by_cutoff")
    if len(features) != len(base) or features.duplicated(BASE_KEYS).any():
        raise DataValidationError("VLE feature aggregation changed row cardinality")
    return features, {
        "sample_vle_rows_before_exact_deduplication": raw_sample_event_rows,
        "sample_vle_exact_duplicate_rows_removed": exact_duplicates,
        "sample_vle_events_by_cutoff_after_deduplication": int(eligible.shape[0]),
        "sample_vle_resource_keys_unmatched": unmatched_resources,
        "sample_vle_learner_course_keys_without_base_record": unmatched_event_keys,
    }


def construct_target(base: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Map the Phase 1 outcome proposal and exclude unknown outcomes."""
    mapped = base["final_result"].map(TARGET_MAP)
    eligible = base.loc[mapped.notna()].copy()
    eligible["target_withdrawn"] = mapped.loc[mapped.notna()].astype("int8")
    excluded = int(mapped.isna().sum())
    return eligible.drop(columns="final_result"), excluded


def model_feature_columns(dataset: pd.DataFrame) -> list[str]:
    """Return candidate predictors, excluding identifiers and the target."""
    excluded = set(BASE_KEYS + ["target_withdrawn", "final_result", "date_unregistration"])
    return [col for col in dataset.columns if col not in excluded]


def validate_final_dataset(dataset: pd.DataFrame) -> dict[str, int]:
    missing_keys = [col for col in BASE_KEYS + ["target_withdrawn"] if col not in dataset]
    if missing_keys:
        raise DataValidationError(f"Final dataset is missing required columns: {', '.join(missing_keys)}")
    _require_key_values(dataset, "final dataset", BASE_KEYS)
    _assert_unique(dataset, BASE_KEYS, "Final feature dataset")
    forbidden = {"final_result", "date_unregistration", "target_withdrawn"}.intersection(model_feature_columns(dataset))
    if forbidden:
        raise DataValidationError(f"Leakage or target column(s) present in model features: {', '.join(sorted(forbidden))}")
    if not dataset["target_withdrawn"].isin([0, 1]).all():
        raise DataValidationError("target_withdrawn contains values other than 0 and 1")
    return {
        "final_rows": len(dataset),
        "final_columns": len(dataset.columns),
        "unique_learners": int(dataset["id_student"].nunique()),
        "final_composite_key_duplicates": int(dataset.duplicated(BASE_KEYS).sum()),
    }


def _sample_eligible_learners(dataset: pd.DataFrame, sample_learners: int | None, seed: int) -> pd.DataFrame:
    if sample_learners is None or sample_learners >= dataset["id_student"].nunique():
        return dataset.copy()
    if sample_learners < 1:
        raise ValueError("sample_learners must be a positive integer or None")
    selected = dataset["id_student"].drop_duplicates().sample(n=sample_learners, random_state=seed)
    return dataset.loc[dataset["id_student"].isin(selected)].copy()


def _missing_summary(dataset: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"column": col, "missing_count": int(dataset[col].isna().sum()),
         "missing_pct": round(100 * dataset[col].isna().mean(), 4)}
        for col in dataset.columns
    ]


def _feature_dictionary(dataset: pd.DataFrame) -> pd.DataFrame:
    definitions: dict[str, tuple[str, str, str, str, str]] = {
        "id_student": ("studentInfo", "Identifier retained for the analysis key.", "Not a predictor", "identifier_only", "Do not provide to a model."),
        "code_module": ("studentInfo", "Course/module code for the base record.", "Available at presentation start", "candidate", "Categorical context; assess temporal generalization."),
        "code_presentation": ("studentInfo", "Course presentation code for the base record.", "Available at presentation start", "candidate", "Categorical context; assess temporal generalization."),
        "gender": ("studentInfo", "Source demographic field retained for fairness analysis.", "Available at presentation start", "requires_fairness_review", "Sensitive/proxy attribute; review before use."),
        "region": ("studentInfo", "Source region category.", "Available at presentation start", "requires_fairness_review", "May proxy sensitive attributes; review before use."),
        "highest_education": ("studentInfo", "Highest education category.", "Available at presentation start", "candidate", "Check missingness and fairness."),
        "imd_band": ("studentInfo", "Index of multiple deprivation band.", "Available at presentation start", "requires_fairness_review", "Socioeconomic proxy; review fairness and privacy."),
        "age_band": ("studentInfo", "Age band.", "Available at presentation start", "requires_fairness_review", "Sensitive attribute; review fairness and privacy."),
        "num_of_prev_attempts": ("studentInfo", "Prior attempts as recorded in the base table.", "Available at presentation start", "candidate", "Confirm intended semantics."),
        "studied_credits": ("studentInfo", "Credit load as recorded in the base table.", "Available at presentation start", "candidate", "None identified."),
        "disability": ("studentInfo", "Disability indicator retained for fairness analysis.", "Available at presentation start", "requires_fairness_review", "Sensitive attribute; review fairness and privacy."),
        "module_presentation_length": ("courses", "Presentation length in days from course metadata.", "Available at presentation start", "candidate", "Course metadata."),
        "registration_record_present": ("studentRegistration", "Whether a registration row exists for the base key.", "Observed in source; validate operational availability", "requires_validation", "Row absence is represented separately from date missingness."),
        "registration_by_cutoff": ("studentRegistration", "1 when date_registration is present and <= cutoff; otherwise 0.", "By cutoff", "candidate", "No unregistration date used."),
        "registration_day_at_cutoff": ("studentRegistration", "date_registration retained only when <= cutoff; future registration dates become missing.", "By cutoff only", "candidate", "Do not impute indiscriminately."),
        "registration_date_missing": ("studentRegistration", "Indicator for missing date_registration.", "By cutoff/source availability", "candidate", "Missing date is not interpreted as completion."),
        "assessments_due_by_cutoff": ("assessments", "Count of assessment metadata rows with nonmissing date <= cutoff.", "By cutoff", "candidate", "Unknown due dates are not counted."),
        "assessment_submissions_by_cutoff": ("studentAssessment + assessments", "Distinct assessments with date_submitted <= cutoff.", "By cutoff", "candidate", "Does not depend on whether score is present."),
        "assessment_banked_results_by_cutoff": ("studentAssessment", "Distinct is_banked=1 results with date_submitted <= cutoff.", "Before/by cutoff per relative date; validate", "requires_validation", "Banked results are not current submissions; the source marks them with date_submitted=-1."),
        "assessment_late_submissions_by_cutoff": ("studentAssessment + assessments", "Submissions by cutoff whose submission day is after the known due day.", "By cutoff", "candidate", "Only known due dates are compared."),
        "assessments_without_submission_recorded_by_cutoff": ("assessments + studentAssessment", "Due assessments <= cutoff with no current submission record and no banked result.", "By cutoff", "requires_validation", "Not proof of a confirmed missed assessment; banked results are treated as previously credited."),
        "assessment_submission_rate_by_cutoff": ("assessments + studentAssessment", "Current due submissions by cutoff / (due assessments - due assessments with a banked result); missing when the denominator is zero.", "By cutoff", "requires_validation", "Absence of a record is not confirmed non-submission."),
        "vle_total_clicks_by_cutoff": ("studentVle", "Sum of sum_click where date <= cutoff after exact duplicate row removal.", "By cutoff inclusive", "candidate", "Negative relative dates are retained; exact source duplicates removed."),
        "vle_active_days_by_cutoff": ("studentVle", "Distinct activity days where date <= cutoff.", "By cutoff inclusive", "candidate", "Includes relative days before day 0 if recorded."),
        "vle_distinct_resources_by_cutoff": ("studentVle", "Distinct id_site values where date <= cutoff.", "By cutoff inclusive", "candidate", "Resource keys validated against vle.csv."),
        "vle_clicks_day_0_7": ("studentVle", "Clicks for relative days 0 through 7 inclusive.", "By cutoff if cutoff >= 7", "candidate", "Defined early-course window."),
        "vle_clicks_day_8_cutoff": ("studentVle", "Clicks for relative days 8 through configured cutoff inclusive.", "By cutoff", "candidate", "Defined only for days >= 8."),
        "vle_has_activity_by_cutoff": ("studentVle", "1 if any activity row is observed on or before cutoff.", "By cutoff inclusive", "candidate", "No row in the supplied event table is treated as no observed activity."),
        "vle_days_since_last_activity_at_cutoff": ("studentVle", "cutoff day minus latest observed activity day <= cutoff; missing when no activity exists.", "By cutoff inclusive", "candidate", "No activity remains missing, not zero."),
        "target_withdrawn": ("studentInfo.final_result", "Withdrawn=1; Pass/Fail/Distinction=0; other outcomes excluded.", "Target only", "target_only", "Never use as predictor; team target proposal remains provisional."),
    }
    rows = []
    for col in dataset.columns:
        source, calculation, availability, status, notes = definitions.get(
            col, ("studentInfo", "Retained source context field.", "Available at presentation start", "candidate", "Review missingness and fairness."))
        rows.append({
            "feature_name": col, "source_table": source, "calculation": calculation,
            "data_type": str(dataset[col].dtype), "available_by_cutoff": availability,
            "missing_value_behavior": "Preserve as missing; count/categorical handling is a modeling-stage decision.",
            "leakage_status": status, "notes": notes,
        })
    rows.extend([
        {"feature_name": "final_result", "source_table": "studentInfo", "calculation": "Used only to create target_withdrawn.",
         "data_type": "string/category", "available_by_cutoff": "Outcome only", "missing_value_behavior": "Unexpected/missing outcomes excluded.",
         "leakage_status": "exclude_due_to_leakage", "notes": "Never included in exported dataset or model feature columns."},
        {"feature_name": "date_unregistration", "source_table": "studentRegistration", "calculation": "Not used.",
         "data_type": "numeric source field", "available_by_cutoff": "Unknown/future", "missing_value_behavior": "Not used.",
         "leakage_status": "exclude_due_to_leakage", "notes": "Can reveal withdrawal; not copied to the feature table."},
        {"feature_name": "assessment score summaries", "source_table": "studentAssessment", "calculation": "Omitted because score release timing is absent.",
         "data_type": "numeric source field", "available_by_cutoff": "Cannot verify", "missing_value_behavior": "No score-derived predictor created.",
         "leakage_status": "exclude_pending_timing_validation", "notes": "Submission timing alone does not prove the score was available by cutoff."},
    ])
    return pd.DataFrame(rows)


def prepare_dataset(
    tables: dict[str, pd.DataFrame], cutoff_day: float = 30,
    sample_learners: int | None = 6000, seed: int = 42,
) -> PreparationResult:
    """Prepare an eligible, optionally learner-sampled dataset and aggregate report."""
    if not np.isfinite(cutoff_day) or cutoff_day < 0:
        raise ValueError("cutoff_day must be a finite non-negative number")
    input_counts = validate_input_tables(tables)
    base_all = build_base_table(tables["studentInfo.csv"], tables["courses.csv"])
    registration_features, registration_metrics = build_registration_features(
        base_all, tables["studentRegistration.csv"], cutoff_day)
    base_all, registration_merge = _merge_one_to_one(base_all, registration_features, "registration")
    targeted, excluded_unknown = construct_target(base_all)
    eligible_learners = int(targeted["id_student"].nunique())
    sampled = _sample_eligible_learners(targeted, sample_learners, seed)
    selected_learners = int(sampled["id_student"].nunique())

    assessment_features, assessment_metrics = build_assessment_features(
        sampled, tables["assessments.csv"], tables["studentAssessment.csv"], cutoff_day, base_all)
    sampled, assessment_merge = _merge_one_to_one(sampled, assessment_features, "assessment")
    vle_features, vle_metrics = build_vle_features(
        sampled, tables["studentVle.csv"], tables["vle.csv"], cutoff_day, base_all)
    sampled, vle_merge = _merge_one_to_one(sampled, vle_features, "VLE")

    sampled = sampled.sort_values(BASE_KEYS, kind="mergesort").reset_index(drop=True)
    key_stats = validate_final_dataset(sampled)
    counts = sampled["target_withdrawn"].value_counts().to_dict()
    total = len(sampled)
    target_distribution = {
        "0": {"count": int(counts.get(0, 0)), "proportion": (counts.get(0, 0) / total if total else 0.0)},
        "1": {"count": int(counts.get(1, 0)), "proportion": (counts.get(1, 0) / total if total else 0.0)},
    }
    report: dict[str, Any] = {
        "input_row_counts": input_counts,
        "base_rows": len(base_all),
        "base_unique_learners": int(base_all["id_student"].nunique()),
        "eligible_rows_before_sampling": len(targeted),
        "eligible_unique_learners_before_sampling": eligible_learners,
        "unknown_target_rows_excluded": excluded_unknown,
        "requested_sample_learners": sample_learners,
        "sample_seed": seed,
        "sampled_unique_learners": selected_learners,
        "sampled_base_rows": len(sampled),
        "target_distribution": target_distribution,
        "cutoff_day_inclusive": cutoff_day,
        "merge_checks": [
            {"feature_table": "course_metadata", "rows_before": len(tables["studentInfo.csv"]),
             "rows_after": len(base_all), "unmatched_base_rows": 0},
            registration_merge, assessment_merge, vle_merge,
        ],
        "registration_checks": registration_metrics,
        "assessment_checks": assessment_metrics,
        "vle_checks": vle_metrics,
        "assessment_scores_missing_in_input": int(tables["studentAssessment.csv"]["score"].isna().sum()),
        **key_stats,
        "missing_output_values": _missing_summary(sampled),
        "feature_columns": model_feature_columns(sampled),
        "warnings": [
            "Day 30 is a provisional Phase 1 cutoff, not team-approved; the boundary day is included.",
            "Assessment scores are omitted because score-release availability by cutoff cannot be verified.",
            "assessments_without_submission_recorded_by_cutoff is not proof of a confirmed missed assessment.",
            "Age, gender, region, disability and IMD attributes require privacy/fairness review.",
            "Exact duplicate VLE rows within selected learners are removed; same-key rows with differing clicks are retained and summed.",
        ],
    }
    dictionary = _feature_dictionary(sampled)
    return PreparationResult(sampled, report, dictionary)


def write_outputs(
    result: PreparationResult, output_path: str | Path,
    report_path: str | Path, feature_dictionary_path: str | Path,
    data_dir: str | Path,
) -> None:
    """Write the learner-level dataset and aggregate-only documentation."""
    output = Path(output_path).expanduser().resolve()
    input_dir = Path(data_dir).expanduser().resolve()
    report_file = Path(report_path).expanduser().resolve()
    dictionary_file = Path(feature_dictionary_path).expanduser().resolve()
    paths = (output, report_file, dictionary_file)
    if len(set(paths)) != len(paths):
        raise ValueError("Output dataset, preparation report, and feature dictionary must use distinct paths")
    for path in paths:
        try:
            path.relative_to(input_dir)
        except ValueError:
            pass
        else:
            raise ValueError("Processed dataset and report paths must be outside the raw input data directory")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    result.dataset.to_csv(output, index=False)
    result.feature_dictionary.to_csv(dictionary_file, index=False)
    root = Path(__file__).resolve().parents[2]
    def display_path(original: str | Path, resolved: Path) -> str:
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            return str(original)
    report_file.write_text(
        _render_report(result.report, display_path(output_path, output), display_path(feature_dictionary_path, dictionary_file)),
        encoding="utf-8",
    )


def _render_report(report: dict[str, Any], output_path: str, dictionary_path: str) -> str:
    target = report["target_distribution"]
    lines = [
        "# Phase 2 OULAD preparation report", "",
        f"- Cutoff: day {report['cutoff_day_inclusive']} inclusive.",
        "- Target: Withdrawn=1; Pass/Fail/Distinction=0; missing/unsupported outcomes excluded.",
        f"- Requested sample: {report['requested_sample_learners']} unique learners; seed {report['sample_seed']}.",
        f"- Final dataset: {report['final_rows']:,} rows × {report['final_columns']:,} columns.",
        f"- Unique learners in output: {report['unique_learners']:,}.",
        f"- Composite-key duplicate rows: {report['final_composite_key_duplicates']:,}.",
        f"- Processed data: `{output_path}`.", f"- Feature dictionary: `{dictionary_path}`.", "",
        "## Input row counts", "", "| Table | Rows |", "|---|---:|",
    ]
    lines.extend(f"| `{name}` | {count:,} |" for name, count in report["input_row_counts"].items())
    lines.extend([
        "", "## Row counts and target", "",
        f"- Base rows: {report['base_rows']:,} ({report['base_unique_learners']:,} unique learners).",
        f"- Target-eligible rows before sampling: {report['eligible_rows_before_sampling']:,}.",
        f"- Unknown/missing target rows excluded: {report['unknown_target_rows_excluded']:,}.",
        f"- Sampled output base rows: {report['sampled_base_rows']:,} across {report['sampled_unique_learners']:,} unique learners.",
        "", "| target_withdrawn | count | proportion |", "|---:|---:|---:|",
        f"| 0 | {target['0']['count']:,} | {target['0']['proportion']:.4%} |",
        f"| 1 | {target['1']['count']:,} | {target['1']['proportion']:.4%} |",
        "", "## Merge validation", "",
        "| Aggregate | Rows before | Rows after | Unmatched base rows |",
        "|---|---:|---:|---:|",
    ])
    lines.extend(f"| {m['feature_table']} | {m['rows_before']:,} | {m['rows_after']:,} | {m['unmatched_base_rows']:,} |"
                 for m in report["merge_checks"])
    lines.extend(["", "## Missing values in output", "", "| Column | Missing | Percent |", "|---|---:|---:|"])
    lines.extend(f"| `{m['column']}` | {m['missing_count']:,} | {m['missing_pct']:.4f}% |"
                 for m in report["missing_output_values"] if m["missing_count"])
    if not any(m["missing_count"] for m in report["missing_output_values"]):
        lines.append("| None | 0 | 0.0000% |")
    lines.extend(["", "## Join and data checks", ""])
    lines.append(f"- Missing assessment scores in source: {report['assessment_scores_missing_in_input']:,}; scores are not predictors because their release time is unavailable.")
    for section in ("registration_checks", "assessment_checks", "vle_checks"):
        lines.extend(f"- {key}: {value:,}." for key, value in report[section].items())
    lines.extend(["", "## Assumptions and warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.extend([
        "", "Assessment due dates use `assessments.date`; submissions use `studentAssessment.date_submitted`; "
        "VLE and registration dates are relative-day values. Every event feature uses `date <= cutoff` (inclusive). "
        "Negative relative days are retained for total activity/registration features because they were observed before the cutoff; "
        "the separate early-activity windows begin at day 0. No absolute calendar dates are inferred.", "",
    ])
    return "\n".join(lines)


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def nonnegative_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not np.isfinite(result) or result < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return result


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=project_root / "ml" / "data" / "raw",
                        help="Directory containing the seven OULAD CSV files")
    parser.add_argument("--output", type=Path, default=project_root / "ml" / "data" / "processed" / "oulad_learner_features.csv")
    parser.add_argument("--cutoff-day", type=nonnegative_float, default=30,
                        help="Inclusive relative course day used for features (default: 30)")
    parser.add_argument("--sample-learners", type=positive_int, default=6000,
                        help="Unique eligible learners to sample (default: 6000; use a value >= population for all)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report", type=Path, default=project_root / "ml" / "reports" / "phase2_preparation_report.md")
    parser.add_argument("--feature-dictionary", type=Path, default=project_root / "ml" / "reports" / "phase2_feature_dictionary.csv")
    args = parser.parse_args(argv)
    try:
        print("Loading and validating OULAD inputs...", flush=True)
        tables = load_oulad_tables(args.data_dir)
        result = prepare_dataset(tables, args.cutoff_day, args.sample_learners, args.seed)
        write_outputs(result, args.output, args.report, args.feature_dictionary, args.data_dir)
    except (FileNotFoundError, DataValidationError, ValueError, pd.errors.MergeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Prepared {result.report['final_rows']:,} rows across {result.report['unique_learners']:,} unique learners.")
    print(f"Cutoff: day {args.cutoff_day} inclusive; sample seed: {args.seed}.")
    print(f"Output: {Path(args.output).expanduser().resolve()}")
    print(f"Target counts: {result.report['target_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
