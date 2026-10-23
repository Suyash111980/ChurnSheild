"""Canonical, leakage-aware feature contract for the OULAD baseline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "oulad-learner-v1.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VERSION = _SCHEMA["schema_version"]
TARGET_COLUMN = _SCHEMA["target_column"]
IDENTIFIER_COLUMNS = list(_SCHEMA["identifier_columns"])
CATEGORICAL_FEATURES = list(_SCHEMA["categorical_features"])
NUMERIC_FEATURES = list(_SCHEMA["numeric_features"])
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
BASE_KEYS = IDENTIFIER_COLUMNS
FORBIDDEN_FEATURES = {
    "id_student", "student_name", "final_result", "target_withdrawn", "date_unregistration",
    "gender", "region", "highest_education", "imd_band", "age_band", "disability",
}


class FeatureContractError(ValueError):
    """Input rows do not conform to the versioned feature contract."""


def validate_feature_frame(
    records: pd.DataFrame | list[dict[str, Any]], *, allow_extra: bool = False
) -> pd.DataFrame:
    """Return a copy in canonical order or reject an incompatible contract."""
    frame = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
    if not len(frame):
        raise FeatureContractError("At least one learner feature record is required")
    missing = [column for column in FEATURE_COLUMNS if column not in frame]
    if missing:
        raise FeatureContractError(f"Missing canonical feature columns: {', '.join(missing)}")
    forbidden = sorted(FORBIDDEN_FEATURES.intersection(frame.columns))
    if forbidden:
        raise FeatureContractError(
            f"Identifiers, outcomes, or protected attributes cannot be model inputs: {', '.join(forbidden)}"
        )
    extras = [column for column in frame.columns if column not in FEATURE_COLUMNS]
    if extras and not allow_extra:
        raise FeatureContractError(f"Unexpected model input columns: {', '.join(extras)}")
    result = frame.loc[:, FEATURE_COLUMNS].copy()
    for column in NUMERIC_FEATURES:
        converted = pd.to_numeric(result[column], errors="coerce")
        malformed = result[column].notna() & converted.isna()
        if malformed.any():
            raise FeatureContractError(f"Numeric feature {column} contains malformed non-missing values")
        if not np.isfinite(converted.dropna().to_numpy(dtype=float)).all():
            raise FeatureContractError(f"Numeric feature {column} contains non-finite values")
        result[column] = converted
    for column in CATEGORICAL_FEATURES:
        # Keep missing categorical values as NumPy NaN. The training-fitted
        # SimpleImputer in the saved pipeline expects a conventional missing
        # marker; pandas.NA raises ``boolean value of NA is ambiguous`` inside
        # scikit-learn's object-array missing-value checks.
        values = result[column].astype("string").str.strip()
        values = values.mask(values.eq(""), pd.NA)
        result[column] = values.astype(object).where(values.notna(), np.nan)
    return result


def validate_training_frame(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Validate prepared rows and return features, labels, and learner groups."""
    required = IDENTIFIER_COLUMNS + [TARGET_COLUMN] + FEATURE_COLUMNS
    missing = [column for column in required if column not in dataset]
    if missing:
        raise FeatureContractError(f"Prepared dataset is missing columns: {', '.join(missing)}")
    if dataset[IDENTIFIER_COLUMNS].isna().any().any():
        raise FeatureContractError("Learner-course identifiers must not be missing")
    if dataset.duplicated(IDENTIFIER_COLUMNS).any():
        raise FeatureContractError("Prepared rows must be unique by learner, module, and presentation")
    labels = pd.to_numeric(dataset[TARGET_COLUMN], errors="coerce")
    if labels.isna().any() or not labels.isin([0, 1]).all():
        raise FeatureContractError("target_withdrawn must contain only binary values 0 and 1")
    features = validate_feature_frame(dataset[FEATURE_COLUMNS])
    groups = dataset["id_student"].astype("string")
    return features, labels.astype("int8"), groups
