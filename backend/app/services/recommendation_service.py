
"""Read persisted recommendations and validate status transitions."""

from datetime import datetime, timezone
from typing import Any

from app.repositories import recommendation_repository


ALLOWED_TRANSITIONS = {
    "pending": {"in_progress", "dismissed"},
    "in_progress": {"completed", "dismissed"},
    "completed": set(),
    "dismissed": set(),
}


def list_recommendations(**filters: Any) -> dict[str, Any]:
    response = recommendation_repository.list_recommendations(**filters)

    rows = [
        {key: value for key, value in row.items() if key != "learners"}
        for row in (response.data or [])
    ]

    total = response.count if response.count is not None else len(rows)

    return {
        "data": rows,
        "limit": filters["limit"],
        "offset": filters["offset"],
        "count": len(rows),
        "total": total,
        "has_more": filters["offset"] + len(rows) < total,
    }


def update_status(
    recommendation_id: str, dataset_id: str, next_status: str
) -> dict[str, Any] | None:
    current = recommendation_repository.get_recommendation(
        recommendation_id, dataset_id
    )

    if current is None:
        return None

    current_status = current.get("status")

    if next_status == current_status:
        return {
            key: value for key, value in current.items()
            if key != "learners"
        }

    if next_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError("invalid_transition")

    learner_id = current.get("learner_id")
    if not isinstance(learner_id, str) or not learner_id:
        # The scoped lookup should include its learner FK. Do not mutate if
        # that verified scope cannot be carried into the conditional update.
        return None

    return recommendation_repository.set_recommendation_status(
        recommendation_id,
        learner_id,
        current_status,
        next_status,
        datetime.now(timezone.utc).isoformat(),
    )
