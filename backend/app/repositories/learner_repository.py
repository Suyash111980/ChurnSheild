
"""Supabase access for learner-course records and their latest snapshots."""

from typing import Any
from types import SimpleNamespace

from app.integrations.supabase_client import supabase


LEARNER_VIEW = "learners_latest_prediction"


def list_learners(
    *,
    dataset_id: str | None,
    limit: int,
    offset: int,
    id_student: str | None = None,
    code_module: str | None = None,
    code_presentation: str | None = None,
    risk_category: str | None = None,
    dataset_ids: list[str] | None = None,
    search: str | None = None,
    sort: str | None = None,
    direction: str = "asc",
):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    query = supabase.table(LEARNER_VIEW).select("*", count="exact")
    if dataset_ids is not None:
        if not dataset_ids:
            return SimpleNamespace(data=[], count=0)
        query = query.in_("dataset_id", dataset_ids)
    else:
        query = query.eq("dataset_id", dataset_id)

    for field, value in (
        ("external_learner_id", id_student),
        ("code_module", code_module),
        ("code_presentation", code_presentation),
        ("latest_risk_category", risk_category),
    ):
        if value is not None:
            query = query.eq(field, value)

    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.or_(
            f"external_learner_id.ilike.%{escaped}%,"
            f"code_module.ilike.%{escaped}%,code_presentation.ilike.%{escaped}%"
        )

    order_fields = {
        "id_student": "external_learner_id",
        "code_module": "code_module",
        "code_presentation": "code_presentation",
        "highest_education": "highest_education",
        "region": "region",
        "latest_risk_probability": "latest_risk_probability",
        "latest_risk_category": "latest_risk_category",
    }
    if sort in order_fields:
        query = query.order(order_fields[sort], desc=direction == "desc", nullsfirst=False)
        query = query.order("id")
    else:
        query = query.order("created_at", desc=True).order("id", desc=True)

    return (
        query.range(offset, offset + limit - 1)
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


def export_risk_predictions(dataset_id: str, *, limit: int):
    """Return only learner-course rows with an actual latest saved prediction."""
    if supabase is None:
        raise RuntimeError("database_unavailable")
    return (
        supabase.table(LEARNER_VIEW)
        .select(
            "external_learner_id, code_module, code_presentation, latest_prediction_id, "
            "latest_model_version, latest_risk_probability, latest_risk_category, "
            "latest_prediction_created_at",
            count="exact",
        )
        .eq("dataset_id", dataset_id)
        .not_.is_("latest_prediction_id", "null")
        .order("external_learner_id")
        .order("code_module")
        .order("code_presentation")
        .range(0, limit - 1)
        .execute()
    )


def list_course_insight_rows(
    dataset_id: str, *, dataset_ids: list[str] | None = None, page_size: int = 1000
) -> list[dict[str, Any]]:
    """Read learner/course keys and latest saved risk values for authorized datasets."""
    if supabase is None:
        raise RuntimeError("database_unavailable")
    if dataset_ids is not None and not dataset_ids:
        return []

    rows: list[dict[str, Any]] = []
    dataset_scopes = (
        [dataset_ids[offset:offset + 100] for offset in range(0, len(dataset_ids), 100)]
        if dataset_ids is not None else [None]
    )
    for scope_ids in dataset_scopes:
        offset = 0
        while True:
            query = (
                supabase.table(LEARNER_VIEW)
                .select("id, dataset_id, code_module, code_presentation, latest_prediction_id, latest_risk_probability, latest_risk_category")
            )
            query = query.in_("dataset_id", scope_ids) if scope_ids is not None else query.eq("dataset_id", dataset_id)
            response = query.order("id").range(offset, offset + page_size - 1).execute()
            batch = response.data or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
    return rows


def list_early_warning(
    *,
    dataset_id: str | None,
    dataset_ids: list[str] | None = None,
    limit: int,
    offset: int,
    risk_category: str | None = None,
    code_module: str | None = None,
    code_presentation: str | None = None,
    search: str | None = None,
):
    if supabase is None:
        raise RuntimeError("database_unavailable")

    query = (
        supabase.table(LEARNER_VIEW)
        .select("*", count="exact")
    )
    if dataset_ids is not None:
        if not dataset_ids:
            return SimpleNamespace(data=[], count=0)
        query = query.in_("dataset_id", dataset_ids)
    elif dataset_id is not None:
        query = query.eq("dataset_id", dataset_id)

    for field, value in (
        ("latest_risk_category", risk_category),
        ("code_module", code_module),
        ("code_presentation", code_presentation),
    ):
        if value is not None:
            query = query.eq(field, value)

    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.or_(
            f"external_learner_id.ilike.%{escaped}%,"
            f"code_module.ilike.%{escaped}%,code_presentation.ilike.%{escaped}%"
        )

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
    learner_ids: list[str], dataset_id: str | None, dataset_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    if not learner_ids:
        return []

    query = (
        supabase.table("learner_latest_feature_snapshot")
        .select("learner_id, as_of_date, features, feature_created_at")
        .in_("learner_id", learner_ids)
    )
    if dataset_ids is not None:
        if not dataset_ids:
            return []
        query = query.in_("dataset_id", dataset_ids)
    elif dataset_id is not None:
        query = query.eq("dataset_id", dataset_id)
    response = query.execute()

    return response.data or []


def get_latest_recommendations(
    learner_ids: list[str], dataset_id: str | None, dataset_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("database_unavailable")

    if not learner_ids:
        return []

    query = (
        supabase.table("learner_latest_recommendation")
        .select("*")
        .in_("learner_id", learner_ids)
    )
    if dataset_ids is not None:
        if not dataset_ids:
            return []
        query = query.in_("dataset_id", dataset_ids)
    elif dataset_id is not None:
        query = query.eq("dataset_id", dataset_id)
    response = query.execute()

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
