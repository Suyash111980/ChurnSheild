import csv
import io

import pytest
from openpyxl import Workbook

from app.integrations.feature_contract import feature_columns
from app.utils.dataset_parser import (
    MAX_UPLOAD_BYTES,
    DatasetUploadError,
    parse_dataset,
)


def canonical_rows():
    rows = []
    for number in range(2):
        row = {
            "id_student": f"00{number + 1}",
            "code_module": "AAA",
            "code_presentation": "2014J",
            "target_withdrawn": str(number),
        }
        row.update({column: "1" for column in feature_columns() if column not in row})
        rows.append(row)
    return rows


def csv_bytes(rows, columns=None):
    columns = columns or list(rows[0])
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def test_csv_uses_shared_schema_and_keeps_source_ids_as_text():
    parsed = parse_dataset("cohort.csv", csv_bytes(canonical_rows()))
    assert parsed.report["descriptive_compatible"] is True
    assert parsed.report["prediction_compatible"] is True
    assert parsed.frame.loc[0, "id_student"] == "001"
    assert parsed.report["preview"][0]["id_student"] == "001"
    assert any(warning["code"] == "target_column_ignored" for warning in parsed.report["warnings"])


def test_missing_model_features_are_descriptive_only():
    rows = canonical_rows()
    rows = [{key: value for key, value in row.items() if key != "vle_total_clicks_by_cutoff"} for row in rows]
    parsed = parse_dataset("cohort.csv", csv_bytes(rows))
    assert parsed.report["descriptive_compatible"] is True
    assert parsed.report["prediction_compatible"] is False
    assert "vle_total_clicks_by_cutoff" in parsed.report["missing_prediction_columns"]


def test_duplicate_source_key_and_invalid_numeric_values_are_reported():
    rows = canonical_rows()
    rows[1]["id_student"] = rows[0]["id_student"]
    rows[1]["vle_total_clicks_by_cutoff"] = "not numeric"
    parsed = parse_dataset("cohort.csv", csv_bytes(rows))
    error_codes = {error["code"] for error in parsed.report["errors"]}
    assert "duplicate_learner_course_keys" in error_codes
    assert "invalid_numeric_values" in error_codes
    assert parsed.report["descriptive_compatible"] is False
    assert parsed.report["prediction_compatible"] is False


def test_xlsx_content_is_read_without_extracting_files(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    headers = list(canonical_rows()[0])
    sheet.append(headers)
    sheet.append([canonical_rows()[0][name] for name in headers])
    stream = io.BytesIO()
    workbook.save(stream)
    parsed = parse_dataset("cohort.xlsx", stream.getvalue())
    assert parsed.report["row_count"] == 1
    assert parsed.report["prediction_compatible"] is True


@pytest.mark.parametrize(
    ("filename", "content", "status_code"),
    [
        ("cohort.exe", b"not data", 415),
        ("cohort.xlsx", b"not a zip", 422),
        ("cohort.csv", b"PK\x03\x04not csv", 422),
        ("cohort.csv", b"\xff\xfe", 422),
    ],
)
def test_unsupported_or_misidentified_file_content_is_rejected(filename, content, status_code):
    with pytest.raises(DatasetUploadError) as error:
        parse_dataset(filename, content)
    assert error.value.status_code == status_code


def test_upload_size_limit_is_enforced():
    with pytest.raises(DatasetUploadError) as error:
        parse_dataset("cohort.csv", b"x" * (MAX_UPLOAD_BYTES + 1))
    assert error.value.status_code == 413


def test_missing_required_keys_return_actionable_errors():
    parsed = parse_dataset("partial.csv", b"name,score\nA,1\n")
    assert {issue["column"] for issue in parsed.report["errors"] if issue.get("code") == "missing_required_column"} == {
        "id_student", "code_module", "code_presentation"
    }
    assert parsed.report["descriptive_compatible"] is False


def test_single_column_csv_returns_required_column_feedback():
    parsed = parse_dataset("partial.csv", b"learner_name\nA\n")
    assert parsed.report["columns"] == ["learner_name"]
    assert {issue["column"] for issue in parsed.report["errors"]} == {
        "id_student", "code_module", "code_presentation"
    }


def test_duplicate_csv_headers_are_reported_without_pandas_renaming():
    parsed = parse_dataset(
        "duplicate.csv",
        b"id_student,id_student,code_module,code_presentation\n001,002,AAA,2014J\n",
    )
    assert parsed.report["columns"] == [
        "id_student", "id_student", "code_module", "code_presentation"
    ]
    assert parsed.report["errors"][0]["code"] == "duplicate_columns"
    assert parsed.report["descriptive_compatible"] is False
