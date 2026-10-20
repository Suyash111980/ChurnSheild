
"""Read-only Supabase access for persisted predictions and explanations."""

from typing import Any

from app.integrations.feature_contract import feature_columns
from app.integrations.supabase_client import supabase


PREDICTION_SELECT = (
    "*, learners!inner"
    "(id, id_student:external_learner_id, code_module, code_presentation, dataset_id)"
)
EXPLANATION_ORDER = {name: index for index, name in enumerate(feature_columns())}


def _ordered_explanations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        ({key: value for key, value in row.items() if key != "predictions"} for row in rows),
        key=lambda row: EXPLANATION_ORDER.get(row.get("feature_name"), len(EXPLANATION_ORDER)),
    )


def list_predictions(
    *,
    dataset_id: str,
    limit: int,
    offset: int,
    risk_category: str | None = None,
    code_module: str | None = None,
    code_presentation: str | None = None,
    learner_id: str | None = None,
):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    query = (
        supabase.table("predictions")
        .select(PREDICTION_SELECT, count="exact")
    )

    for field, value in (
        ("risk_category", risk_category),
        ("learners.code_module", code_module),
        ("learners.code_presentation", code_presentation),
        ("learner_id", learner_id),
        ("learners.dataset_id", dataset_id),
    ):
        if value is not None:
            query = query.eq(field, value)

    return (
        query.order("created_at", desc=True)
        .order("id", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )


def get_prediction(
    prediction_id: str,
    dataset_id: str,
) -> dict[str, Any] | None:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    response = (
        supabase.table("predictions")
        .select(PREDICTION_SELECT)
        .eq("id", prediction_id)
        .eq("learners.dataset_id", dataset_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return rows[0] if rows else None


def list_explanations(
    prediction_id: str,
    dataset_id: str,
) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    response = (
        supabase.table("risk_explanations")
        .select(
            "id, prediction_id, feature_name, feature_value, contribution, created_at, "
            "predictions!inner(learners!inner(dataset_id))"
        )
        .eq("prediction_id", prediction_id)
        .eq("predictions.learners.dataset_id", dataset_id)
        .order("feature_name")
        .execute()
    )

    return _ordered_explanations(response.data or [])


def list_explanations_for_predictions(
    prediction_ids: list[str],
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Return explanations only for predictions in the selected dataset."""
    if supabase is None:
        raise RuntimeError("database_unavailable")

    if not prediction_ids:
        return []

    response = (
        supabase.table("risk_explanations")
        .select(
            "id, prediction_id, feature_name, feature_value, contribution, created_at, "
            "predictions!inner(learners!inner(dataset_id))"
        )
        .in_("prediction_id", prediction_ids)
        .eq("predictions.learners.dataset_id", dataset_id)
        .order("feature_name")
        # Early Warning is capped at 100 learner rows; the canonical schema
        # currently has 22 features per prediction (at most 2,200 rows).
        .limit(2500)
        .execute()
    )

    return _ordered_explanations(response.data or [])
