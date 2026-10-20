import csv

import pytest

from app.core.config import settings
from app.services import student_display_service as display


@pytest.fixture(autouse=True)
def clear_display_cache():
    display._load_lookup.cache_clear()
    yield
    display._load_lookup.cache_clear()


def configure_path(monkeypatch, path):
    monkeypatch.setattr(settings, "student_display_csv_path", str(path))


def write_csv(path, rows, columns=None):
    columns = columns or ["id_student", "code_module", "code_presentation", "student_name"]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_composite_key_distinguishes_presentations(monkeypatch, tmp_path):
    path = tmp_path / "student_display.csv"
    write_csv(
        path,
        [
            {"id_student": " 00123 ", "code_module": "AAA", "code_presentation": "2014J", "student_name": " Casey "},
            {"id_student": "00123", "code_module": "BBB", "code_presentation": "2014B", "student_name": "Jordan"},
        ],
    )
    configure_path(monkeypatch, path)

    assert display.get_student_name(
        {"id_student": "00123", "code_module": "AAA", "code_presentation": "2014J"}
    ) == "Casey"
    assert display.get_student_name(
        {"id_student": "00123", "code_module": "BBB", "code_presentation": "2014B"}
    ) == "Jordan"
    assert display.get_student_name(
        {"id_student": "00123", "code_module": "AAA", "code_presentation": "2014B"}
    ) is None


def test_attach_names_adds_nullable_display_field_without_changing_keys(monkeypatch, tmp_path):
    path = tmp_path / "student_display.csv"
    write_csv(path, [{"id_student": "1", "code_module": "A", "code_presentation": "P", "student_name": "Demo Name"}])
    configure_path(monkeypatch, path)

    result = display.attach_student_names(
        [{"id": "uuid", "id_student": "1", "code_module": "A", "code_presentation": "P"},
         {"id": "uuid2", "id_student": "2", "code_module": "A", "code_presentation": "P"}]
    )

    assert result[0]["student_name"] == "Demo Name"
    assert result[1]["student_name"] is None
    assert result[0]["id"] == "uuid"


def test_missing_csv_and_missing_or_empty_name_return_none(monkeypatch, tmp_path):
    missing = tmp_path / "absent.csv"
    configure_path(monkeypatch, missing)
    learner = {"id_student": "1", "code_module": "A", "code_presentation": "P"}
    assert display.get_student_name(learner) is None

    write_csv(missing, [{**learner, "student_name": "  "}])
    display._load_lookup.cache_clear()
    assert display.get_student_name(learner) is None


def test_invalid_header_and_unreadable_file_are_optional(monkeypatch, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("student_id,name\n1,Name\n", encoding="utf-8")
    configure_path(monkeypatch, path)
    assert display.get_display_name_lookup() == {}

    configure_path(monkeypatch, tmp_path)
    assert display.get_display_name_lookup() == {}


def test_duplicate_same_name_is_kept_but_conflict_is_ambiguous(monkeypatch, tmp_path):
    path = tmp_path / "duplicates.csv"
    key = {"id_student": "1", "code_module": "A", "code_presentation": "P"}
    write_csv(path, [{**key, "student_name": "Name"}, {**key, "student_name": "Name"}])
    configure_path(monkeypatch, path)
    assert display.get_student_name(key) == "Name"

    write_csv(path, [{**key, "student_name": "Name"}, {**key, "student_name": "Other"}])
    display._load_lookup.cache_clear()
    assert display.get_student_name(key) is None


def test_duplicate_headers_are_rejected(monkeypatch, tmp_path):
    path = tmp_path / "duplicate_headers.csv"
    path.write_text(
        "id_student,id_student,code_module,code_presentation,student_name\n1,1,A,P,Name\n",
        encoding="utf-8",
    )
    configure_path(monkeypatch, path)
    assert display.get_display_name_lookup() == {}
