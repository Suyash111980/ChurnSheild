"""Bounded CSV export of owner-scoped, persisted learner predictions."""

import csv
import io

from app.repositories import learner_repository

MAX_EXPORT_ROWS = 10_000


class ReportTooLarge(ValueError):
    pass


def _spreadsheet_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def export_learner_csv(dataset_id: str) -> tuple[str, int]:
    response = learner_repository.export_learners(dataset_id, limit=MAX_EXPORT_ROWS)
    rows = response.data or []
    total = response.count
    if total is not None and total > MAX_EXPORT_ROWS:
        raise ReportTooLarge("This dataset exceeds the 10,000-row export limit")
    if total is None and len(rows) >= MAX_EXPORT_ROWS:
        raise ReportTooLarge("Dataset size could not be verified for export")
    output = io.StringIO(newline="")
    columns = (
        "id_student", "code_module", "code_presentation", "risk_probability",
        "risk_category", "prediction_created_at",
    )
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "id_student": _spreadsheet_safe(row.get("id_student")),
            "code_module": _spreadsheet_safe(row.get("code_module")),
            "code_presentation": _spreadsheet_safe(row.get("code_presentation")),
            "risk_probability": _spreadsheet_safe(row.get("latest_risk_probability")),
            "risk_category": _spreadsheet_safe(row.get("latest_risk_category")),
            "prediction_created_at": _spreadsheet_safe(row.get("latest_prediction_created_at")),
        })
    return output.getvalue(), len(rows)
