"""Database-free tests for the OULAD source-to-import field mapping."""

import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_oulad_learners.py"
SPEC = importlib.util.spec_from_file_location("import_oulad_learners", SCRIPT_PATH)
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


def test_source_student_identifier_is_kept_in_import_payload():
    frame = pd.DataFrame(
        [
            {
                "id_student": "123456789",
                "code_module": "AAA",
                "code_presentation": "2014J",
                "gender": "F",
                "region": "East Anglian Region",
                "highest_education": "HE Qualification",
                "imd_band": "10-20%",
                "age_band": "0-35",
                "num_of_prev_attempts": 0,
                "studied_credits": 60,
                "disability": "N",
            }
        ]
    )

    [record] = IMPORTER.prepare_records(frame)

    assert record["id_student"] == "123456789"
    assert "external_learner_id" not in record
    assert record["code_module"] == "AAA"
    assert record["code_presentation"] == "2014J"
