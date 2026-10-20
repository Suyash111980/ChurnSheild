"""Deterministic learner-grouped train/validation/test split helpers."""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import GroupShuffleSplit


def grouped_train_validation_test_indices(groups, *, seed: int = 42):
    """Split learners, never rows, into approximately 60/20/20 partitions."""
    groups = np.asarray(groups, dtype=str)
    if len(groups) < 10 or len(np.unique(groups)) < 10:
        raise ValueError("At least 10 distinct learner groups are required for a holdout split")

    test_split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_validation, test = next(test_split.split(np.zeros(len(groups)), groups=groups))
    remaining_groups = groups[train_validation]
    validation_split = GroupShuffleSplit(
        n_splits=1, test_size=0.25, random_state=seed + 1
    )
    train_relative, validation_relative = next(
        validation_split.split(np.zeros(len(train_validation)), groups=remaining_groups)
    )
    train = train_validation[train_relative]
    validation = train_validation[validation_relative]

    partitions = [set(groups[index]) for index in (train, validation, test)]
    if any(partitions[i] & partitions[j] for i in range(3) for j in range(i + 1, 3)):
        raise RuntimeError("Learner group leakage detected across data partitions")
    return train, validation, test
