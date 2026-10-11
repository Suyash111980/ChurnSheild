import pandas as pd
import pytest

from ml.src.prepare_oulad import (
    DataValidationError,
    load_oulad_tables,
    validate_input_tables,
)


def test_load_missing_required_csv_has_actionable_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="studentInfo.csv") as error:
        load_oulad_tables(tmp_path)
    assert "--data-dir" in str(error.value)


def test_missing_required_table_is_reported(sample_tables):
    del sample_tables["vle.csv"]
    with pytest.raises(DataValidationError, match="vle.csv"):
        validate_input_tables(sample_tables)


def test_missing_required_column_is_reported(sample_tables):
    sample_tables["studentInfo.csv"] = sample_tables["studentInfo.csv"].drop(columns="code_presentation")
    with pytest.raises(DataValidationError, match="code_presentation"):
        validate_input_tables(sample_tables)


def test_empty_input_table_is_rejected(sample_tables):
    sample_tables["studentVle.csv"] = sample_tables["studentVle.csv"].iloc[:0]
    with pytest.raises(DataValidationError, match="studentVle.csv is empty"):
        validate_input_tables(sample_tables)


def test_non_numeric_event_date_is_rejected(sample_tables):
    sample_tables["studentVle.csv"]["date"] = sample_tables["studentVle.csv"]["date"].astype(object)
    sample_tables["studentVle.csv"].loc[0, "date"] = "after-course"
    with pytest.raises(DataValidationError, match="studentVle.csv.date must contain numeric"):
        validate_input_tables(sample_tables)


def test_missing_key_value_is_rejected(sample_tables):
    sample_tables["studentInfo.csv"].loc[0, "id_student"] = None
    with pytest.raises(DataValidationError, match="missing or blank values"):
        validate_input_tables(sample_tables)


def test_duplicate_base_composite_key_is_rejected(sample_tables):
    sample_tables["studentInfo.csv"] = pd.concat(
        [sample_tables["studentInfo.csv"], sample_tables["studentInfo.csv"].iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="studentInfo.csv.*duplicate row"):
        validate_input_tables(sample_tables)


def test_duplicate_assessment_metadata_is_rejected(sample_tables):
    sample_tables["assessments.csv"] = pd.concat(
        [sample_tables["assessments.csv"], sample_tables["assessments.csv"].iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="assessments.csv.*duplicate row"):
        validate_input_tables(sample_tables)


def test_duplicate_student_assessment_event_is_rejected(sample_tables):
    sample_tables["studentAssessment.csv"] = pd.concat(
        [sample_tables["studentAssessment.csv"], sample_tables["studentAssessment.csv"].iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="studentAssessment.csv.*duplicate row"):
        validate_input_tables(sample_tables)


def test_unknown_final_results_are_retained_for_explicit_target_exclusion(sample_tables):
    stats = validate_input_tables(sample_tables)
    assert stats["studentInfo.csv"] == 5
    assert sample_tables["studentInfo.csv"].loc[3, "final_result"] == "In Progress"
