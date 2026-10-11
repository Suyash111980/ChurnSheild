import pandas as pd

from ml.src.prepare_oulad import prepare_dataset, validate_input_tables


def _result(tables):
    validate_input_tables(tables)
    return prepare_dataset(tables, cutoff_day=30, sample_learners=None, seed=42).dataset


def test_future_vle_and_assessment_changes_do_not_change_features(sample_tables):
    baseline = _result(sample_tables)
    changed = {name: frame.copy(deep=True) for name, frame in sample_tables.items()}
    changed["studentVle.csv"].loc[changed["studentVle.csv"].date.eq(31), "sum_click"] = 99999
    changed["studentAssessment.csv"].loc[changed["studentAssessment.csv"].date_submitted.gt(30), "score"] = 1.0
    future = _result(changed)
    pd.testing.assert_frame_equal(baseline, future)


def test_unregistration_is_never_a_feature(sample_tables):
    baseline = _result(sample_tables)
    changed = {name: frame.copy(deep=True) for name, frame in sample_tables.items()}
    changed["studentRegistration.csv"]["date_unregistration"] = [-300, 5, 30, 100, 200]
    changed_result = _result(changed)
    pd.testing.assert_frame_equal(baseline, changed_result)
    assert "date_unregistration" not in changed_result


def test_future_registration_day_does_not_enter_output(sample_tables):
    baseline = _result(sample_tables)
    changed = {name: frame.copy(deep=True) for name, frame in sample_tables.items()}
    registration = changed["studentRegistration.csv"]
    registration.loc[registration.id_student.eq(2), "date_registration"] = 200
    pd.testing.assert_frame_equal(baseline, _result(changed))


def test_target_and_identifiers_are_excluded_from_model_feature_list(sample_tables):
    result = _result(sample_tables)
    features = result.columns.difference(["id_student", "code_module", "code_presentation", "target_withdrawn"])
    assert "target_withdrawn" not in features
    assert "final_result" not in features
    assert "id_student" not in features
    assert "date_unregistration" not in features


def test_cutoff_day_events_are_included_and_day_after_is_excluded(sample_tables):
    data = _result(sample_tables).set_index("id_student")
    assert data.loc[1, "vle_total_clicks_by_cutoff"] == 9
    assert data.loc[3, "assessment_submissions_by_cutoff"] == 1
    assert data.loc[3, "assessment_late_submissions_by_cutoff"] == 1


def test_assessment_score_features_are_omitted_without_release_date(sample_tables):
    result = _result(sample_tables)
    assert not any("score" in column.lower() for column in result.columns)
