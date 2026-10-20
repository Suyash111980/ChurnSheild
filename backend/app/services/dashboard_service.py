"""Dataset-scoped descriptive summaries backed by persisted DB records."""

from app.repositories import dataset_repository


def get_summary(dataset_id: str, owner_id: str, workspace_id: str) -> dict | None:
    dataset = dataset_repository.get_owned_dataset(dataset_id, owner_id, workspace_id)
    if dataset is None:
        return None
    row = dataset_repository.get_dashboard_summary(dataset_id)
    if row is None:
        return None
    total = int(row.get("total_learner_records") or 0)
    with_prediction = int(row.get("learners_with_prediction") or 0)
    has_predictions = with_prediction > 0
    coverage = with_prediction / total if total else None
    return {
        "dataset_id": dataset_id,
        "total_learner_records": total,
        "course_presentation_count": int(row.get("course_presentation_count") or 0),
        "learners_with_prediction": with_prediction,
        "prediction_coverage": coverage,
        "risk_distribution": (
            {
                "low": int(row.get("low_risk_count") or 0),
                "medium": int(row.get("medium_risk_count") or 0),
                "high": int(row.get("high_risk_count") or 0),
            }
            if has_predictions else None
        ),
        "prediction_state": "available" if has_predictions else "not_available",
        "descriptive_statistics": {
            "learner_course_records": total,
            "course_presentations": int(row.get("course_presentation_count") or 0),
        },
    }
