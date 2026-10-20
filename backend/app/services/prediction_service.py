"""Prediction read-response composition; inference is a separate boundary."""

from typing import Any

from app.repositories import prediction_repository
from app.services.student_display_service import attach_student_names


def _with_display_name(row: dict[str, Any]) -> dict[str, Any]:
    learner = row.get("learners")
    if not isinstance(learner, dict):
        return {**row, "student_name": None}
    enriched = attach_student_names([learner])[0]
    return {**row, "learners": enriched, "student_name": enriched["student_name"]}


def list_predictions(**filters: Any) -> dict[str, Any]:
    response = prediction_repository.list_predictions(**filters)
    rows = [_with_display_name(row) for row in (response.data or [])]
    total = response.count if response.count is not None else len(rows)
    return {
        "data": rows,
        "limit": filters["limit"],
        "offset": filters["offset"],
        "count": len(rows),
        "total": total,
        "has_more": filters["offset"] + len(rows) < total,
    }


def get_prediction(prediction_id: str, dataset_id: str) -> dict[str, Any] | None:
    row = prediction_repository.get_prediction(prediction_id, dataset_id)
    return _with_display_name(row) if row else None


def list_explanations(prediction_id: str, dataset_id: str) -> list[dict[str, Any]]:
    return prediction_repository.list_explanations(prediction_id, dataset_id)
