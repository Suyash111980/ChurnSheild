"""Database-free tests for the OULAD source-to-import field mapping."""

import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_oulad_learners.py"
SPEC = importlib.util.spec_from_file_location("import_oulad_learners", SCRIPT_PATH)
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


def test_oulad_source_id_maps_to_canonical_database_column_and_dataset():
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

    dataset_id = "723a41ce-7f26-4f3e-99b5-e950b62c5fb9"
    [record] = IMPORTER.prepare_records(frame, dataset_id=dataset_id)

    assert record["external_learner_id"] == "123456789"
    assert record["dataset_id"] == dataset_id
    assert "id_student" not in record
    assert record["code_module"] == "AAA"
    assert record["code_presentation"] == "2014J"
