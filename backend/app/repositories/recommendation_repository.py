"""Supabase data access for existing recommendation records."""

from typing import Any

from app.integrations.supabase_client import supabase


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
        "*, learners!inner(dataset_id)", count="exact"
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
