from __future__ import annotations

import pandas as pd
import pytest

from ml.src.features.build_features import NUMERIC_FEATURES
from ml.src.training.day30_experiment import build_day30_cohort, temporal_grouped_indices


def _feature_rows():
    rows = []
    for learner, result in enumerate((0, 1, 0, 1, 0, 1, 0, 1)):
        row = {
            "id_student": str(learner),
            "code_module": "AAA",
            "code_presentation": "2014J",
            "target_withdrawn": result,
        }
        row.update({column: float(learner + offset) for offset, column in enumerate(NUMERIC_FEATURES)})
        rows.append(row)
    return pd.DataFrame(rows)


def test_day30_cohort_excludes_early_and_untimed_withdrawals():
    features = _feature_rows()
    registration = pd.DataFrame({
        "id_student": [str(i) for i in range(8)],
        "code_module": ["AAA"] * 8,
        "code_presentation": ["2014J"] * 8,
        "date_registration": [-10, -10, 31, -10, -10, -10, None, -10],
        "date_unregistration": [None, 31, None, 30, None, None, None, 40],
    })

    cohort, report = build_day30_cohort(features, registration, cutoff_day=30)

    assert cohort.id_student.tolist() == ["0", "1", "4", "7"]
    assert "date_unregistration" not in cohort
    assert report["eligible_rows"] == 4
    assert report["excluded_unregistered_on_or_before_cutoff"] == 1
    assert report["excluded_withdrawn_target_without_timed_unregistration"] == 1
    assert report["eligible_target_counts"] == {"0": 2, "1": 2}


def test_temporal_split_is_forward_only_and_learner_disjoint():
    rows = []
    for presentation, start in (("2013B", 0), ("2013J", 10), ("2014B", 20), ("2014J", 30)):
        for offset in range(10):
            learner = start + offset
            row = {
                "id_student": str(learner),
                "code_module": "AAA",
                "code_presentation": presentation,
                "target_withdrawn": offset % 2,
            }
            row.update({column: float(learner + index) for index, column in enumerate(NUMERIC_FEATURES)})
            rows.append(row)
    # Include repeat learners across time; they must be removed from earlier partitions.
    for presentation, learner in (("2014B", 0), ("2014J", 10), ("2014J", 20)):
        row = next(item for item in rows if item["id_student"] == str(learner))
        repeated = dict(row)
        repeated["code_presentation"] = presentation
        rows.append(repeated)
    data = pd.DataFrame(rows)

    train, validation, test, report = temporal_grouped_indices(data)

    train_groups = set(data.iloc[train].id_student)
    validation_groups = set(data.iloc[validation].id_student)
    test_groups = set(data.iloc[test].id_student)
    assert not train_groups & validation_groups
    assert not train_groups & test_groups
    assert not validation_groups & test_groups
    assert set(data.iloc[train].code_presentation).issubset({"2013B", "2013J"})
    assert set(data.iloc[validation].code_presentation) == {"2014B"}
    assert set(data.iloc[test].code_presentation) == {"2014J"}
    assert report["learner_groups_disjoint"] is True


def test_day30_cohort_rejects_duplicate_registration_keys():
    data = _feature_rows()
    registration = pd.DataFrame({
        "id_student": ["0", "0"],
        "code_module": ["AAA", "AAA"],
        "code_presentation": ["2014J", "2014J"],
        "date_registration": [0, 0],
        "date_unregistration": [None, None],
    })
    with pytest.raises(ValueError, match="unique"):
        build_day30_cohort(data, registration)
