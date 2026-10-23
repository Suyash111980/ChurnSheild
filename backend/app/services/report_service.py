"""Bounded CSV export of owner-scoped, persisted learner predictions."""

import csv
import io

from app.repositories import learner_repository

MAX_EXPORT_ROWS = 10_000


class ReportTooLarge(ValueError):
    pass


class ReportUnavailable(ValueError):
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
    if not rows:
        raise ReportUnavailable("No learner records are available for this dataset.")
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


def export_risk_analysis_csv(dataset_id: str) -> tuple[str, int]:
    response = learner_repository.export_risk_predictions(dataset_id, limit=MAX_EXPORT_ROWS)
    rows = response.data or []
    total = response.count
    if total is not None and total > MAX_EXPORT_ROWS:
        raise ReportTooLarge("This dataset exceeds the 10,000-row export limit")
    if total is None and len(rows) >= MAX_EXPORT_ROWS:
        raise ReportTooLarge("Risk report size could not be verified")
    if not rows:
        raise ReportUnavailable("No saved predictions are available for this dataset.")

    output = io.StringIO(newline="")
    fields = (
        "learner_id", "code_module", "code_presentation", "prediction_id",
        "model_version", "risk_probability", "risk_category", "prediction_created_at",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "learner_id": _spreadsheet_safe(row.get("external_learner_id")),
            "code_module": _spreadsheet_safe(row.get("code_module")),
            "code_presentation": _spreadsheet_safe(row.get("code_presentation")),
            "prediction_id": _spreadsheet_safe(row.get("latest_prediction_id")),
            "model_version": _spreadsheet_safe(row.get("latest_model_version")),
            "risk_probability": _spreadsheet_safe(row.get("latest_risk_probability")),
            "risk_category": _spreadsheet_safe(row.get("latest_risk_category")),
            "prediction_created_at": _spreadsheet_safe(row.get("latest_prediction_created_at")),
        })
    return output.getvalue(), len(rows)


def export_recommendations_csv(dataset_id: str) -> tuple[str, int]:
    from app.repositories import recommendation_repository

    rows, total = recommendation_repository.export_dataset_recommendations(
        dataset_id, limit=MAX_EXPORT_ROWS
    )
    if total > MAX_EXPORT_ROWS:
        raise ReportTooLarge("This dataset exceeds the 10,000-row export limit")
    if not rows:
        raise ReportUnavailable("No saved recommendations are available for this dataset.")

    output = io.StringIO(newline="")
    fields = (
        "recommendation_id", "learner_id", "code_module", "code_presentation",
        "prediction_id", "rule_id", "action", "reason", "status", "created_at", "updated_at",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        learner = row.get("learners") if isinstance(row.get("learners"), dict) else {}
        writer.writerow({
            "recommendation_id": _spreadsheet_safe(row.get("id")),
            "learner_id": _spreadsheet_safe(learner.get("external_learner_id") or row.get("learner_id")),
            "code_module": _spreadsheet_safe(learner.get("code_module")),
            "code_presentation": _spreadsheet_safe(learner.get("code_presentation")),
            "prediction_id": _spreadsheet_safe(row.get("prediction_id")),
            "rule_id": _spreadsheet_safe(row.get("rule_id")),
            "action": _spreadsheet_safe(row.get("action")),
            "reason": _spreadsheet_safe(row.get("reason")),
            "status": _spreadsheet_safe(row.get("status")),
            "created_at": _spreadsheet_safe(row.get("created_at")),
            "updated_at": _spreadsheet_safe(row.get("updated_at")),
        })
    return output.getvalue(), len(rows)
