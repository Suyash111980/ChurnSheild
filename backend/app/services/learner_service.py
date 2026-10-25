
"""Learner API composition and optional display-name enrichment."""

from typing import Any

from app.repositories import learner_repository
from app.repositories import prediction_repository
from app.services.recommendation_service import recommendation_to_api_record
from app.services.student_display_service import (
    attach_student_names,
    get_student_name,
)


def _with_api_source_identifier(row: dict[str, Any]) -> dict[str, Any]:
    """Keep the existing API field while the database uses its canonical name."""
    if row.get("id_student") is None and row.get("external_learner_id") is not None:
        return {**row, "id_student": row["external_learner_id"]}
    return row


def list_learners(**filters: Any) -> dict[str, Any]:
    response = learner_repository.list_learners(**filters)
    rows = attach_student_names(
        [_with_api_source_identifier(row) for row in (response.data or [])]
    )
    total = response.count if response.count is not None else len(rows)

    return {
        "data": rows,
        "limit": filters["limit"],
        "offset": filters["offset"],
        "count": len(rows),
        "total": total,
        "has_more": filters["offset"] + len(rows) < total,
    }


def get_learner_profile(
    learner_id: str,
    dataset_id: str,
) -> dict[str, Any] | None:
    learner = learner_repository.get_learner(learner_id, dataset_id)

    if learner is None:
        return None
    learner = _with_api_source_identifier(learner)

    prediction = None
    prediction_id = learner.get("latest_prediction_id")
    explanations: list[dict[str, Any]] = []

    if prediction_id:
        prediction = {
            "id": prediction_id,
            "learner_id": learner_id,
            "model_version": learner.get("latest_model_version"),
            "risk_probability": learner.get("latest_risk_probability"),
            "risk_category": learner.get("latest_risk_category"),
            "created_at": learner.get("latest_prediction_created_at"),
        }

        explanations = prediction_repository.list_explanations(
            str(prediction_id), dataset_id
        )

    feature = learner_repository.get_latest_feature_snapshot(
        learner_id,
        dataset_id,
    )

    recommendations = learner_repository.list_recommendations_for_learner(
        learner_id,
        dataset_id,
    )
    recommendation_rows = [
        {**recommendation_to_api_record(row), "learners": row.get("learners")}
        for row in (recommendations.data or [])
    ]

    learner = {
        key: value
        for key, value in learner.items()
        if not key.startswith("latest_")
    }

    return {
        "learner": learner,
        "student_name": get_student_name(learner),
        "latest_feature_snapshot": feature,
        "latest_prediction": prediction,
        "risk_explanations": explanations,
        "recommendations": recommendation_rows,
    }


def get_early_warning_page(**filters: Any) -> dict[str, Any]:
    response = learner_repository.list_early_warning(**filters)
    rows = [_with_api_source_identifier(row) for row in (response.data or [])]

    dataset_id = filters.get("dataset_id")
    dataset_ids = filters.get("dataset_ids")

    learner_ids = [row["id"] for row in rows]

    prediction_ids = [
        row["latest_prediction_id"]
        for row in rows
        if row.get("latest_prediction_id")
    ]

    features_by_learner = {
        row["learner_id"]: row
        for row in learner_repository.get_latest_feature_snapshots(
            learner_ids,
            dataset_id,
            dataset_ids,
        )
    }

    recommendations_by_learner = {
        row["learner_id"]: row
        for row in learner_repository.get_latest_recommendations(
            learner_ids,
            dataset_id,
            dataset_ids,
        )
    }

    explanations_by_prediction: dict[str, list[dict[str, Any]]] = {}

    explanations = prediction_repository.list_explanations_for_predictions(
        [str(value) for value in prediction_ids],
        dataset_id,
        dataset_ids,
    )

    for explanation in explanations:
        explanations_by_prediction.setdefault(
            explanation["prediction_id"],
            [],
        ).append(explanation)

    enriched = []

    for row in rows:
        prediction_id = row.get("latest_prediction_id")

        enriched.append(
            {
                **row,
                "student_name": get_student_name(row),
                "prediction_state": (
                    "available" if prediction_id else "unavailable"
                ),
                "latest_feature_snapshot": features_by_learner.get(
                    row["id"]
                ),
                "latest_explanations": (
                    explanations_by_prediction.get(
                        str(prediction_id),
                        [],
                    )
                    if prediction_id
                    else []
                ),
                "latest_recommendation": recommendations_by_learner.get(
                    row["id"]
                ),
            }
        )

    total = (
        response.count
        if response.count is not None
        else len(enriched)
    )

    return {
        "data": enriched,
        "limit": filters["limit"],
        "offset": filters["offset"],
        "count": len(enriched),
        "total": total,
        "has_more": filters["offset"] + len(enriched) < total,
    }
