"""Supabase data access for existing recommendation records."""

from typing import Any

from app.integrations.supabase_client import supabase

RECOMMENDATION_STATUSES = ("pending", "in_progress", "completed", "dismissed")


def list_recommendations(
    *,
    dataset_id: str,
    limit: int,
    offset: int,
    learner_id: str | None = None,
    prediction_id: str | None = None,
    recommendation_status: str | None = None,
):
    if supabase is None:
        raise RuntimeError("database_unavailable")
    query = supabase.table("recommendations").select(
        "*, learners!inner(dataset_id, external_learner_id, code_module, code_presentation)", count="exact"
    ).eq("learners.dataset_id", dataset_id)
    for field, value in (
        ("learner_id", learner_id),
        ("prediction_id", prediction_id),
        ("status", recommendation_status),
    ):
        if value is not None:
            query = query.eq(field, value)
    return (
        query.order("created_at", desc=True)
        .order("id", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )


def count_recommendations_by_status(
    *,
    dataset_id: str,
    learner_id: str | None = None,
    prediction_id: str | None = None,
) -> dict[str, int]:
    """Count persisted statuses for one authorized dataset, without pagination."""
    if supabase is None:
        raise RuntimeError("database_unavailable")

    counts: dict[str, int] = {}
    for recommendation_status in RECOMMENDATION_STATUSES:
        query = (
            supabase.table("recommendations")
            .select("id, learners!inner(dataset_id)", count="exact", head=True)
            .eq("learners.dataset_id", dataset_id)
            .eq("status", recommendation_status)
        )
        if learner_id is not None:
            query = query.eq("learner_id", learner_id)
        if prediction_id is not None:
            query = query.eq("prediction_id", prediction_id)
        response = query.execute()
        counts[recommendation_status] = int(response.count or 0)
    return counts


def export_dataset_recommendations(dataset_id: str, *, limit: int, page_size: int = 500):
    """Read saved recommendations with their verified dataset learner context."""
    if supabase is None:
        raise RuntimeError("database_unavailable")
    rows: list[dict[str, Any]] = []
    total = 0
    offset = 0
    while offset < limit:
        response = (
            supabase.table("recommendations")
            .select(
                "id, learner_id, prediction_id, rule_id, action, reason, status, created_at, updated_at, "
                "learners!inner(dataset_id, external_learner_id, code_module, code_presentation)",
                count="exact",
            )
            .eq("learners.dataset_id", dataset_id)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .range(offset, min(offset + page_size, limit) - 1)
            .execute()
        )
        batch = response.data or []
        if offset == 0:
            total = int(response.count or 0)
        rows.extend(batch)
        if len(batch) < min(page_size, limit - offset):
            break
        offset += len(batch)
    return rows, total


def get_recommendation(recommendation_id: str, dataset_id: str) -> dict[str, Any] | None:
    if supabase is None:
        raise RuntimeError("database_unavailable")
    response = (
        supabase.table("recommendations")
        .select("*, learners!inner(dataset_id)")
        .eq("id", recommendation_id)
        .eq("learners.dataset_id", dataset_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def set_recommendation_status(
    recommendation_id: str, learner_id: str, current_status: str, next_status: str, updated_at: str
) -> dict[str, Any] | None:
    if supabase is None:
        raise RuntimeError("database_unavailable")
    response = (
        supabase.table("recommendations")
        .update({"status": next_status, "updated_at": updated_at})
        .eq("id", recommendation_id)
        .eq("learner_id", learner_id)
        .eq("status", current_status)
        .select("*")
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None
