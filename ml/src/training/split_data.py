"""Reproducible student-grouped train/validation/test splits."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from ml.src.features.model_schema import GROUP_COLUMN, TARGET_COLUMN


def split_dataset(data: pd.DataFrame, seed: int = 42) -> dict[str, np.ndarray]:
    """Split rows into approximately 60/20/20 folds without student overlap."""
    if GROUP_COLUMN not in data:
        raise ValueError(f"Training data must contain grouping column {GROUP_COLUMN!r}")
    if TARGET_COLUMN not in data:
        raise ValueError(f"Training data must contain target column {TARGET_COLUMN!r}")
    if data[GROUP_COLUMN].isna().any():
        raise ValueError(f"Grouping column {GROUP_COLUMN!r} cannot contain missing values")
    if data[TARGET_COLUMN].isna().any() or not set(data[TARGET_COLUMN].unique()).issubset({0, 1}):
        raise ValueError(f"Target {TARGET_COLUMN!r} must contain only non-missing 0/1 labels")
    if data[GROUP_COLUMN].nunique() < 5:
        raise ValueError("At least five unique students are required for grouped train/validation/test splitting")

    y = data[TARGET_COLUMN].astype(int).to_numpy()
    groups = data[GROUP_COLUMN].to_numpy()
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    folds = list(outer.split(np.zeros(len(data)), y, groups))
    train_val_idx, test_idx = folds[0]
    train_val = data.iloc[train_val_idx]
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    inner_folds = list(inner.split(np.zeros(len(train_val)), train_val[TARGET_COLUMN], train_val[GROUP_COLUMN]))
    train_local, validation_local = inner_folds[0]
    result = {
        "train": train_val_idx[train_local],
        "validation": train_val_idx[validation_local],
        "test": test_idx,
    }
    group_sets = {name: set(groups[index]) for name, index in result.items()}
    if (group_sets["train"] & group_sets["validation"] or group_sets["train"] & group_sets["test"]
            or group_sets["validation"] & group_sets["test"]):
        raise RuntimeError("Student group leakage detected between dataset splits")
    for name, indexes in result.items():
        if len(np.unique(y[indexes])) != 2:
            raise ValueError(f"{name} split does not contain both target classes; use more learner records")
    return result
