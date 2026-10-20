
"""Supabase access for learner-course records and their latest snapshots."""

from typing import Any

from app.integrations.supabase_client import supabase


LEARNER_VIEW = "learners_latest_prediction"


def list_learners(
    *,
    dataset_id: str,
    limit: int,
    offset: int,
    id_student: str | None = None,
    code_module: str | None = None,
    code_presentation: str | None = None,
    risk_category: str | None = None,
):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    query = (
        supabase.table(LEARNER_VIEW)
        .select("*", count="exact")
        .eq("dataset_id", dataset_id)
    )

    for field, value in (
        ("external_learner_id", id_student),
        ("code_module", code_module),
        ("code_presentation", code_presentation),
        ("latest_risk_category", risk_category),
    ):
        if value is not None:
            query = query.eq(field, value)

    return (
        query.order("created_at", desc=True)
        .order("id", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )


def export_learners(dataset_id: str, *, limit: int):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    return (
        supabase.table(LEARNER_VIEW)
        .select(
            "id_student:external_learner_id, code_module, code_presentation, latest_risk_probability, "
            "latest_risk_category, latest_prediction_created_at",
            count="exact",
        )
        .eq("dataset_id", dataset_id)
        .order("external_learner_id")
        .order("code_module")
        .order("code_presentation")
        .range(0, limit - 1)
        .execute()
    )


def list_early_warning(
    *,
    dataset_id: str,
    limit: int,
    offset: int,
    risk_category: str | None = None,
    code_module: str | None = None,
    code_presentation: str | None = None,
):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    query = (
        supabase.table(LEARNER_VIEW)
        .select("*", count="exact")
        .eq("dataset_id", dataset_id)
    )

    for field, value in (
        ("latest_risk_category", risk_category),
        ("code_module", code_module),
        ("code_presentation", code_presentation),
    ):
        if value is not None:
            query = query.eq(field, value)

    return (
        query.order("latest_risk_probability", desc=True)
        .order("id", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )


def get_learner(learner_id: str, dataset_id: str) -> dict[str, Any] | None:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    response = (
        supabase.table(LEARNER_VIEW)
        .select("*")
        .eq("id", learner_id)
        .eq("dataset_id", dataset_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return rows[0] if rows else None


def get_latest_feature_snapshot(
    learner_id: str, dataset_id: str
) -> dict[str, Any] | None:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    response = (
        supabase.table("learner_latest_feature_snapshot")
        .select("learner_id, as_of_date, features, feature_created_at")
        .eq("learner_id", learner_id)
        .eq("dataset_id", dataset_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return rows[0] if rows else None


def get_latest_feature_snapshots(
    learner_ids: list[str], dataset_id: str
) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    if not learner_ids:
        return []

    response = (
        supabase.table("learner_latest_feature_snapshot")
        .select("learner_id, as_of_date, features, feature_created_at")
        .in_("learner_id", learner_ids)
        .eq("dataset_id", dataset_id)
        .execute()
    )

    return response.data or []


def get_latest_recommendations(
    learner_ids: list[str], dataset_id: str
) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    if not learner_ids:
        return []

    response = (
        supabase.table("learner_latest_recommendation")
        .select("*")
        .in_("learner_id", learner_ids)
        .eq("dataset_id", dataset_id)
        .execute()
    )

    return response.data or []


def list_recommendations_for_learner(
    learner_id: str, dataset_id: str, *, limit: int = 100
):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    return (
        supabase.table("recommendations")
        .select("*, learners!inner(dataset_id)")
        .eq("learner_id", learner_id)
        .eq("learners.dataset_id", dataset_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
