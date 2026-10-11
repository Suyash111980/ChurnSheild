import pandas as pd
import pytest

from ml.src.prepare_oulad import (
    DataValidationError,
    build_assessment_features,
    build_base_table,
    build_registration_features,
    build_vle_features,
    construct_target,
    model_feature_columns,
    prepare_dataset,
    validate_final_dataset,
    validate_input_tables,
    write_outputs,
)


def _prepare(sample_tables, sample_learners=None, cutoff=30, seed=42):
    validate_input_tables(sample_tables)
    return prepare_dataset(sample_tables, cutoff, sample_learners, seed)


def test_output_has_one_row_per_eligible_composite_key(sample_tables):
    result = _prepare(sample_tables)
    data = result.dataset
    assert len(data) == 4
    assert not data.duplicated(["id_student", "code_module", "code_presentation"]).any()
    assert set(data["id_student"]) == {1, 2, 3, 5}
    assert data["target_withdrawn"].value_counts().to_dict() == {0: 3, 1: 1}
    assert "final_result" not in data
    assert "target_withdrawn" not in model_feature_columns(data)


def test_assessment_features_respect_cutoff_and_known_due_schedule(sample_tables):
    result = _prepare(sample_tables)
    data = result.dataset.set_index("id_student")
    # Due day 10 is included. Day 35 and the unknown date are not due by day 30.
    assert data.loc[1, "assessments_due_by_cutoff"] == 1
    assert data.loc[1, "assessment_submissions_by_cutoff"] == 1  # day-35 submission is excluded
    assert data.loc[1, "assessments_without_submission_recorded_by_cutoff"] == 0
    assert data.loc[2, "assessment_late_submissions_by_cutoff"] == 1
    assert data.loc[3, "assessment_submissions_by_cutoff"] == 1
    assert data.loc[3, "assessment_late_submissions_by_cutoff"] == 1  # day-30 boundary is included
    assert data.loc[5, "assessments_without_submission_recorded_by_cutoff"] == 1
    assert data.loc[5, "assessment_submission_rate_by_cutoff"] == 0


def test_missing_score_does_not_remove_submission_or_become_feature(sample_tables):
    result = _prepare(sample_tables)
    data = result.dataset.set_index("id_student")
    assert pd.isna(sample_tables["studentAssessment.csv"].loc[2, "score"])
    assert data.loc[2, "assessment_submissions_by_cutoff"] == 1
    assert not any("score" in col for col in data.columns)


def test_banked_results_are_not_mistaken_for_current_submissions_or_misses(sample_tables):
    sample_tables["studentAssessment.csv"] = pd.concat([
        sample_tables["studentAssessment.csv"],
        pd.DataFrame([{"id_student": 5, "id_assessment": 10, "date_submitted": -1, "is_banked": 1, "score": 75.0}]),
    ], ignore_index=True)
    result = _prepare(sample_tables)
    row = result.dataset.loc[result.dataset.id_student.eq(5)].iloc[0]
    assert row["assessment_banked_results_by_cutoff"] == 1
    assert row["assessment_submissions_by_cutoff"] == 0
    assert row["assessments_without_submission_recorded_by_cutoff"] == 0
    assert pd.isna(row["assessment_submission_rate_by_cutoff"])


def test_vle_clicks_aggregate_cutoff_boundary_and_deduplicate_exact_rows(sample_tables):
    result = _prepare(sample_tables)
    data = result.dataset.set_index("id_student")
    # Duplicate day-0 record counts once; day 30 is included and day 31 excluded.
    assert data.loc[1, "vle_total_clicks_by_cutoff"] == 9
    assert data.loc[1, "vle_active_days_by_cutoff"] == 3
    assert data.loc[1, "vle_distinct_resources_by_cutoff"] == 2
    assert data.loc[1, "vle_clicks_day_0_7"] == 2
    assert data.loc[1, "vle_clicks_day_8_cutoff"] == 7
    assert data.loc[1, "vle_days_since_last_activity_at_cutoff"] == 0
    assert result.report["vle_checks"]["sample_vle_exact_duplicate_rows_removed"] == 1
    assert result.report["vle_checks"]["sample_vle_events_by_cutoff_after_deduplication"] == 4


def test_same_vle_key_with_distinct_click_rows_is_retained(sample_tables):
    sample_tables["studentVle.csv"] = pd.concat([
        sample_tables["studentVle.csv"],
        pd.DataFrame([{"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "id_site": 100, "date": 0, "sum_click": 3}]),
    ], ignore_index=True)
    result = _prepare(sample_tables)
    row = result.dataset.loc[result.dataset.id_student.eq(1)].iloc[0]
    assert row["vle_total_clicks_by_cutoff"] == 12


def test_learners_without_activity_get_zero_counts_and_missing_last_day(sample_tables):
    data = _prepare(sample_tables).dataset.set_index("id_student")
    row = data.loc[2]
    assert row["vle_total_clicks_by_cutoff"] == 0
    assert row["vle_active_days_by_cutoff"] == 0
    assert row["vle_has_activity_by_cutoff"] == 0
    assert pd.isna(row["vle_days_since_last_activity_at_cutoff"])


def test_registration_features_are_cutoff_safe_and_exclude_unregistration(sample_tables):
    data = _prepare(sample_tables).dataset.set_index("id_student")
    assert data.loc[1, "registration_day_at_cutoff"] == -20
    assert data.loc[1, "registration_by_cutoff"] == 1
    assert data.loc[2, "registration_by_cutoff"] == 0
    assert pd.isna(data.loc[2, "registration_day_at_cutoff"])  # registration on day 40 is future
    assert data.loc[3, "registration_date_missing"] == 1
    assert "date_unregistration" not in data
    assert "date_unregistration" not in model_feature_columns(data)


def test_target_mapping_and_unknown_exclusion(sample_tables):
    result = _prepare(sample_tables)
    assert result.report["unknown_target_rows_excluded"] == 1
    assert set(result.dataset["target_withdrawn"]) == {0, 1}
    assert set(result.dataset.loc[result.dataset.id_student.eq(2), "target_withdrawn"]) == {1}
    assert set(result.dataset.loc[result.dataset.id_student.isin([1, 3, 5]), "target_withdrawn"]) == {0}


def test_sample_size_counts_unique_learners_and_keeps_all_their_rows(sample_tables):
    info = sample_tables["studentInfo.csv"]
    extra = info.iloc[[0]].copy()
    extra["code_presentation"] = "2024J"
    sample_tables["studentInfo.csv"] = pd.concat([info, extra], ignore_index=True)
    sample_tables["courses.csv"] = pd.concat([
        sample_tables["courses.csv"],
        pd.DataFrame([{"code_module": "AAA", "code_presentation": "2024J", "module_presentation_length": 90}]),
    ], ignore_index=True)
    result = _prepare(sample_tables, sample_learners=4)
    assert result.report["sampled_unique_learners"] == 4
    assert len(result.dataset) == 5
    assert result.dataset.id_student.nunique() == 4


def test_sampling_is_deterministic(sample_tables):
    first = _prepare(sample_tables, sample_learners=2, seed=17).dataset
    second = _prepare(sample_tables, sample_learners=2, seed=17).dataset
    pd.testing.assert_frame_equal(first, second)


def test_invalid_assessment_reference_fails_clearly(sample_tables):
    sample_tables["studentAssessment.csv"].loc[0, "id_assessment"] = 999
    validate_input_tables(sample_tables)
    with pytest.raises(DataValidationError, match="unknown id_assessment"):
        prepare_dataset(sample_tables, sample_learners=None)


def test_invalid_vle_resource_reference_fails_clearly(sample_tables):
    sample_tables["studentVle.csv"].loc[0, "id_site"] = 999
    validate_input_tables(sample_tables)
    with pytest.raises(DataValidationError, match="do not match vle.csv"):
        prepare_dataset(sample_tables, sample_learners=None)


def test_vle_event_with_known_resource_but_wrong_learner_course_key_is_reported(sample_tables):
    sample_tables["studentVle.csv"] = pd.concat([
        sample_tables["studentVle.csv"],
        pd.DataFrame([{"id_student": 1, "code_module": "BBB", "code_presentation": "2024J", "id_site": 200, "date": 2, "sum_click": 4}]),
    ], ignore_index=True)
    result = _prepare(sample_tables)
    assert result.report["vle_checks"]["sample_vle_learner_course_keys_without_base_record"] == 1
    row = result.dataset.loc[result.dataset.id_student.eq(1)].iloc[0]
    assert row["vle_total_clicks_by_cutoff"] == 9


def test_duplicate_vle_metadata_key_is_rejected(sample_tables):
    sample_tables["vle.csv"] = pd.concat([sample_tables["vle.csv"], sample_tables["vle.csv"].iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="vle.csv.*duplicate row"):
        validate_input_tables(sample_tables)


def test_registration_and_base_build_keep_expected_cardinality(sample_tables):
    validate_input_tables(sample_tables)
    base = build_base_table(sample_tables["studentInfo.csv"], sample_tables["courses.csv"])
    registration, metrics = build_registration_features(base, sample_tables["studentRegistration.csv"], 30)
    assert len(base) == len(registration) == 5
    assert not registration.duplicated(["id_student", "code_module", "code_presentation"]).any()
    assert metrics["base_records_without_registration_row"] == 0
    assert "module_presentation_length" in base


def test_course_join_cardinality_violation_fails(sample_tables):
    courses = pd.concat([sample_tables["courses.csv"], sample_tables["courses.csv"].iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="duplicate key"):
        build_base_table(sample_tables["studentInfo.csv"], courses)


def test_feature_merge_reports_unmatched_and_rejects_many_to_many(sample_tables):
    from ml.src.prepare_oulad import _merge_one_to_one
    base = pd.DataFrame({"id_student": [1, 2], "code_module": ["A", "A"], "code_presentation": ["P", "P"]})
    features = pd.DataFrame({"id_student": [1], "code_module": ["A"], "code_presentation": ["P"], "x": [4]})
    merged, metrics = _merge_one_to_one(base, features, "test")
    assert len(merged) == 2 and metrics["unmatched_base_rows"] == 1
    duplicated_features = pd.concat([features, features], ignore_index=True)
    with pytest.raises(DataValidationError, match="duplicate key"):
        _merge_one_to_one(base, duplicated_features, "test")


def test_final_validator_rejects_duplicate_composite_keys(sample_tables):
    data = _prepare(sample_tables).dataset
    duplicate = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="duplicate key"):
        validate_final_dataset(duplicate)


def test_final_report_and_feature_dictionary_have_aggregate_definitions(sample_tables):
    result = _prepare(sample_tables)
    assert result.report["final_composite_key_duplicates"] == 0
    assert result.report["final_rows"] == 4
    assert {"feature_name", "source_table", "calculation", "data_type", "available_by_cutoff", "missing_value_behavior", "leakage_status", "notes"}.issubset(result.feature_dictionary.columns)
    assert "exclude_due_to_leakage" in set(result.feature_dictionary.leakage_status)


def test_write_outputs_creates_csv_report_and_feature_dictionary(sample_tables, tmp_path):
    result = _prepare(sample_tables)
    raw = tmp_path / "raw"
    raw.mkdir()
    output = tmp_path / "processed" / "data.csv"
    report = tmp_path / "reports" / "report.md"
    dictionary = tmp_path / "reports" / "features.csv"
    write_outputs(result, output, report, dictionary, raw)
    assert pd.read_csv(output).shape == result.dataset.shape
    assert "day 30 inclusive" in report.read_text(encoding="utf-8")
    assert len(pd.read_csv(dictionary)) == len(result.feature_dictionary)


def test_write_outputs_refuses_raw_input_directory(sample_tables, tmp_path):
    result = _prepare(sample_tables)
    raw = tmp_path / "raw"
    raw.mkdir()
    with pytest.raises(ValueError, match="outside the raw input"):
        write_outputs(result, raw / "features.csv", tmp_path / "r.md", tmp_path / "f.csv", raw)


def test_cutoff_must_be_nonnegative(sample_tables):
    with pytest.raises(ValueError, match="non-negative"):
        prepare_dataset(sample_tables, cutoff_day=-1)
