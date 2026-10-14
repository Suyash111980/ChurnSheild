"""Stable inference feature schema for the Phase 3 model."""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET_COLUMN = "target_withdrawn"
GROUP_COLUMN = "id_student"
IDENTIFIER_COLUMNS = ("id_student", "code_module", "code_presentation")

# These are the Phase 2 day-30 prepared columns, not the seven raw OULAD tables.
CATEGORICAL_FEATURES = (
    "code_module",
    "code_presentation",
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
    "disability",
)
NUMERIC_FEATURES = (
    "num_of_prev_attempts",
    "studied_credits",
    "module_presentation_length",
    "registration_record_present",
    "registration_by_cutoff",
    "registration_day_at_cutoff",
    "registration_date_missing",
    "assessments_due_by_cutoff",
    "assessment_submissions_by_cutoff",
    "assessment_late_submissions_by_cutoff",
    "assessments_without_submission_recorded_by_cutoff",
    "assessment_banked_results_by_cutoff",
    "assessment_submission_rate_by_cutoff",
    "vle_total_clicks_by_cutoff",
    "vle_active_days_by_cutoff",
    "vle_distinct_resources_by_cutoff",
    "vle_clicks_day_0_7",
    "vle_clicks_day_8_cutoff",
    "vle_has_activity_by_cutoff",
    "vle_days_since_last_activity_at_cutoff",
)
RAW_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def validate_feature_frame(frame):
    """Validate required prepared feature columns and numeric compatibility."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Inference input must be a pandas DataFrame of prepared learner features")
    missing = [column for column in RAW_FEATURES if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required model input column(s): {', '.join(missing)}")
    result = frame.loc[:, RAW_FEATURES].copy()
    for column in NUMERIC_FEATURES:
        converted = pd.to_numeric(result[column], errors="coerce")
        invalid = result[column].notna() & converted.isna()
        if invalid.any():
            raise ValueError(f"Model input column {column!r} must contain numeric values or missing values")
        finite = converted.dropna().to_numpy(dtype=float)
        if not np.isfinite(finite).all():
            raise ValueError(f"Model input column {column!r} must contain finite numeric values or missing values")
        result[column] = converted
    for column in CATEGORICAL_FEATURES:
        result[column] = result[column].astype("string").astype(object)
        result.loc[result[column].isna(), column] = float("nan")
    return result
