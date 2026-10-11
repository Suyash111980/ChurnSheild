from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def sample_tables():
    """Small synthetic OULAD-shaped tables; no real learner data is required."""
    return {
        "studentInfo.csv": pd.DataFrame([
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "gender": "F", "region": "North", "highest_education": "A Level", "imd_band": "20-30%", "age_band": "0-35", "num_of_prev_attempts": 0, "studied_credits": 60, "disability": "N", "final_result": "Pass"},
            {"id_student": 2, "code_module": "AAA", "code_presentation": "2024B", "gender": "M", "region": "South", "highest_education": "HE Qualification", "imd_band": None, "age_band": "35-55", "num_of_prev_attempts": 1, "studied_credits": 30, "disability": "N", "final_result": "Withdrawn"},
            {"id_student": 3, "code_module": "BBB", "code_presentation": "2024J", "gender": "F", "region": "West", "highest_education": "A Level", "imd_band": "10-20%", "age_band": "0-35", "num_of_prev_attempts": 0, "studied_credits": 60, "disability": "Y", "final_result": "Fail"},
            {"id_student": 4, "code_module": "BBB", "code_presentation": "2024J", "gender": "M", "region": "East", "highest_education": "Lower Than A Level", "imd_band": "30-40%", "age_band": "35-55", "num_of_prev_attempts": 0, "studied_credits": 30, "disability": "N", "final_result": "In Progress"},
            {"id_student": 5, "code_module": "AAA", "code_presentation": "2024B", "gender": "F", "region": "North", "highest_education": "A Level", "imd_band": "40-50%", "age_band": "0-35", "num_of_prev_attempts": 0, "studied_credits": 30, "disability": "N", "final_result": "Distinction"},
        ]),
        "studentAssessment.csv": pd.DataFrame([
            {"id_student": 1, "id_assessment": 10, "date_submitted": 9, "is_banked": 0, "score": 80.0},
            {"id_student": 1, "id_assessment": 11, "date_submitted": 35, "is_banked": 0, "score": 95.0},
            {"id_student": 2, "id_assessment": 10, "date_submitted": 12, "is_banked": 0, "score": None},
            {"id_student": 3, "id_assessment": 20, "date_submitted": 30, "is_banked": 0, "score": 60.0},
        ]),
        "assessments.csv": pd.DataFrame([
            {"id_assessment": 10, "code_module": "AAA", "code_presentation": "2024B", "date": 10, "assessment_type": "TMA", "weight": 50},
            {"id_assessment": 11, "code_module": "AAA", "code_presentation": "2024B", "date": 35, "assessment_type": "TMA", "weight": 50},
            {"id_assessment": 20, "code_module": "BBB", "code_presentation": "2024J", "date": 20, "assessment_type": "CMA", "weight": 100},
            {"id_assessment": 21, "code_module": "BBB", "code_presentation": "2024J", "date": None, "assessment_type": "Exam", "weight": 0},
        ]),
        "studentVle.csv": pd.DataFrame([
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "id_site": 100, "date": 0, "sum_click": 2},
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "id_site": 100, "date": 0, "sum_click": 2},  # exact source duplicate
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "id_site": 101, "date": 8, "sum_click": 4},
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "id_site": 100, "date": 30, "sum_click": 3},
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "id_site": 100, "date": 31, "sum_click": 100},
            {"id_student": 3, "code_module": "BBB", "code_presentation": "2024J", "id_site": 200, "date": 29, "sum_click": 5},
            {"id_student": 3, "code_module": "BBB", "code_presentation": "2024J", "id_site": 200, "date": 31, "sum_click": 200},
        ]),
        "studentRegistration.csv": pd.DataFrame([
            {"id_student": 1, "code_module": "AAA", "code_presentation": "2024B", "date_registration": -20, "date_unregistration": 80},
            {"id_student": 2, "code_module": "AAA", "code_presentation": "2024B", "date_registration": 40, "date_unregistration": None},
            {"id_student": 3, "code_module": "BBB", "code_presentation": "2024J", "date_registration": None, "date_unregistration": 44},
            {"id_student": 4, "code_module": "BBB", "code_presentation": "2024J", "date_registration": 1, "date_unregistration": None},
            {"id_student": 5, "code_module": "AAA", "code_presentation": "2024B", "date_registration": -1, "date_unregistration": None},
        ]),
        "courses.csv": pd.DataFrame([
            {"code_module": "AAA", "code_presentation": "2024B", "module_presentation_length": 100},
            {"code_module": "BBB", "code_presentation": "2024J", "module_presentation_length": 80},
        ]),
        "vle.csv": pd.DataFrame([
            {"id_site": 100, "code_module": "AAA", "code_presentation": "2024B", "activity_type": "resource"},
            {"id_site": 101, "code_module": "AAA", "code_presentation": "2024B", "activity_type": "forum"},
            {"id_site": 200, "code_module": "BBB", "code_presentation": "2024J", "activity_type": "resource"},
        ]),
    }


@pytest.fixture
def write_tables(tmp_path):
    def write(tables, directory=None):
        data_dir = directory or tmp_path / "raw"
        data_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in tables.items():
            frame.to_csv(data_dir / name, index=False)
        return data_dir
    return write
