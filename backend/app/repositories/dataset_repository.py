"""Supabase persistence for private datasets and their learner records."""

import logging
import re
from typing import Any

from app.integrations.supabase_client import supabase

logger = logging.getLogger(__name__)

DATASET_COLUMNS = (
    "id, owner_id, workspace_id, dataset_name, filename, status, uploaded_at, updated_at, "
    "row_count, file_size_bytes, descriptive_compatible, prediction_compatible, "
    "processing_progress, processed_at, error_summary, validation_results"
)

RECOMMENDATION_COLUMNS = (
    "id, learner_id, prediction_id, rule_id, action, reason, "
    "status, created_at, updated_at"
)

RECOMMENDATION_READBACK_COLUMNS = (
    f"{RECOMMENDATION_COLUMNS}, learners!inner(id, dataset_id)"
)

RECOMMENDATION_CHUNK_SIZE = 100


def _client():
    if supabase is None:
        raise RuntimeError("database_unavailable")
    return supabase


def _log_database_error(operation: str, exc: Exception) -> None:
    """Log safe diagnostic metadata without dumping request or credential data."""
    error_code = getattr(exc, "code", None)

    if isinstance(error_code, int) and not isinstance(error_code, bool):
        error_code = str(error_code)

    if (
        not isinstance(error_code, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", error_code)
    ):
        error_code = "unavailable"

    logger.warning(
        "Database operation %s failed "
        "(exception_type=%s, error_code=%s)",
        operation,
        type(exc).__name__,
        error_code,
    )


def create_dataset(payload: dict):
    response = (
        _client()
        .table("dataset_uploads")
        .insert(payload)
        .select(DATASET_COLUMNS)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def get_workspace_for_admin(owner_id: str):
    response = (
        _client()
        .table("workspaces")
        .select("id, admin_user_id, status")
        .eq("admin_user_id", owner_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def get_owned_dataset(dataset_id: str, owner_id: str, workspace_id: str):
    response = (
        _client()
        .table("dataset_uploads")
        .select(DATASET_COLUMNS)
        .eq("id", dataset_id)
        .eq("owner_id", owner_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def list_owned_datasets(
    *,
    owner_id: str,
    workspace_id: str,
    limit: int,
    offset: int,
):
    return (
        _client()
        .table("dataset_uploads")
        .select(DATASET_COLUMNS, count="exact")
        .eq("owner_id", owner_id)
        .eq("workspace_id", workspace_id)
        .order("uploaded_at", desc=True)
        .order("id", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )


def list_all_owned_datasets(*, owner_id: str, workspace_id: str) -> list[dict]:
    """Read all datasets in one already-verified workspace, using bounded pages."""
    rows: list[dict] = []
    offset = 0
    page_size = 100
    while True:
        response = list_owned_datasets(
            owner_id=owner_id, workspace_id=workspace_id, limit=page_size, offset=offset
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def get_dashboard_summaries(dataset_ids: list[str]) -> list[dict]:
    if not dataset_ids:
        return []
    rows = []
    for offset in range(0, len(dataset_ids), 100):
        response = (
            _client().table("dataset_dashboard_summary")
            .select(
                "dataset_id,total_learner_records,course_presentation_count,learners_with_prediction,"
                "low_risk_count,medium_risk_count,high_risk_count"
            )
            .in_("dataset_id", dataset_ids[offset:offset + 100])
            .execute()
        )
        rows.extend(response.data or [])
    return rows


def update_owned_dataset(dataset_id: str, owner_id: str, workspace_id: str, updates: dict):
    response = (
        _client()
        .table("dataset_uploads")
        .update(updates)
        .eq("id", dataset_id)
        .eq("owner_id", owner_id)
        .eq("workspace_id", workspace_id)
        .select(DATASET_COLUMNS)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def delete_owned_dataset(dataset_id: str, owner_id: str, workspace_id: str, access_token: str):
    """Delete through the authenticated user's JWT so dataset RLS remains active."""
    from supabase import create_client

    from app.core.config import settings

    if not settings.supabase_url.strip() or not settings.supabase_publishable_key.strip():
        raise RuntimeError("database_unavailable")
    client = create_client(settings.supabase_url, settings.supabase_publishable_key)
    client.postgrest.auth(access_token)
    response = (
        client.table("dataset_uploads")
        .delete()
        .eq("id", dataset_id)
        .eq("owner_id", owner_id)
        .eq("workspace_id", workspace_id)
        .neq("status", "processing")
        .select("id")
        .execute()
    )
    rows = response.data or []
    if rows:
        return rows[0]

    # Diagnose an empty DELETE result through the trusted server client, scoped
    # to the same owner/workspace. Never log the dataset ID or identity values.
    try:
        scoped_rows = (
            _client().table("dataset_uploads")
            .select("status")
            .eq("id", dataset_id)
            .eq("owner_id", owner_id)
            .eq("workspace_id", workspace_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not scoped_rows:
            reason = "not_found_or_scope_mismatch"
        elif scoped_rows[0].get("status") == "processing":
            reason = "processing"
        else:
            reason = "policy_denied_or_concurrent_change"
        logger.info("Dataset deletion returned no row (reason=%s)", reason)
    except Exception as exc:
        logger.warning(
            "Dataset deletion returned no row; diagnosis unavailable (exception_type=%s)",
            type(exc).__name__,
        )
    return None


def upsert_learners(records: list[dict]) -> list[dict]:
    if not records:
        return []

    response = (
        _client()
        .table("learners")
        .upsert(
            records,
            on_conflict=(
                "dataset_id,external_learner_id,"
                "code_module,code_presentation"
            ),
        )
        .select(
            "id, dataset_id, external_learner_id, "
            "code_module, code_presentation"
        )
        .execute()
    )
    return response.data or []


def get_dataset_source_keys(dataset_id: str) -> set[tuple[str, str, str]]:
    """Read source learner-course keys for safe in-place dataset enrichment."""
    keys: set[tuple[str, str, str]] = set()
    row_count = 0
    offset = 0
    page_size = 500
    while True:
        response = (
            _client().table("learners")
            .select("external_learner_id,code_module,code_presentation")
            .eq("dataset_id", dataset_id)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data or []
        row_count += len(rows)
        for row in rows:
            source_id = row.get("external_learner_id")
            module = row.get("code_module")
            presentation = row.get("code_presentation")
            if source_id is None or module is None or presentation is None:
                raise RuntimeError("dataset_source_keys_incomplete")
            key = (str(source_id).strip(), str(module).strip(), str(presentation).strip())
            if key in keys:
                raise RuntimeError("dataset_source_keys_duplicate")
            keys.add(key)
        if len(rows) < page_size:
            if row_count != len(keys):
                raise RuntimeError("dataset_source_keys_incomplete")
            return keys
        offset += page_size


def upsert_features(records: list[dict]) -> None:
    if not records:
        return

    (
        _client()
        .table("learner_features")
        .upsert(records, on_conflict="learner_id,as_of_date")
        .execute()
    )


def upsert_predictions(records: list[dict]) -> list[dict]:
    """Persist one current model result per learner and model version."""
    if not records:
        return []

    response = (
        _client()
        .table("predictions")
        .upsert(records, on_conflict="learner_id,model_version")
        .select(
            "id, learner_id, model_version, risk_probability, "
            "risk_category, created_at"
        )
        .execute()
    )
    return response.data or []


def upsert_explanations(records: list[dict]) -> list[dict]:
    """Upsert explanation evidence on the prediction/feature key."""
    if not records:
        return []

    response = (
        _client()
        .table("risk_explanations")
        .upsert(records, on_conflict="prediction_id,feature_name")
        .select(
            "id, prediction_id, feature_name, "
            "feature_value, contribution"
        )
        .execute()
    )
    return response.data or []


def _valid_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _recommendation_key(record: dict) -> tuple[str, str]:
    return record["prediction_id"], record["rule_id"]


def upsert_recommendations(records: list[dict], *, dataset_id: str) -> dict:
    """Persist recommendations and verify their learner/dataset association.

    Requires a unique conflict target on (prediction_id, rule_id).
    Duplicate input keys with conflicting recommendation content are rejected.
    Database errors are logged without exposing credentials or row contents.
    """
    if not records:
        return {"persisted": [], "failed_count": 0}

    client = _client()
    persisted: list[dict] = []
    failed_count = 0

    unique_records: dict[tuple[str, str], dict] = {}
    invalid_keys: set[tuple[str, str]] = set()
    invalid_count = 0

    for record in records:
        if not isinstance(record, dict):
            invalid_count += 1
            continue

        prediction_id = record.get("prediction_id")
        rule_id = record.get("rule_id")
        learner_id = record.get("learner_id")

        if not all(
            _valid_nonempty_string(value)
            for value in (prediction_id, rule_id, learner_id)
        ):
            invalid_count += 1
            continue

        key = (prediction_id, rule_id)
        previous = unique_records.get(key)

        if previous is not None:
            if any(
                previous.get(field) != record.get(field)
                for field in ("learner_id", "action", "reason")
            ):
                invalid_keys.add(key)
            continue

        unique_records[key] = record

    failed_count += invalid_count + len(invalid_keys)

    for key in invalid_keys:
        unique_records.pop(key, None)

    candidates = list(unique_records.values())

    logger.info(
        "Recommendation persistence starting "
        "(input=%d, valid_unique=%d, invalid=%d)",
        len(records),
        len(candidates),
        invalid_count + len(invalid_keys),
    )

    for offset in range(0, len(candidates), RECOMMENDATION_CHUNK_SIZE):
        batch = candidates[offset : offset + RECOMMENDATION_CHUNK_SIZE]

        try:
            (
                client.table("recommendations")
                .upsert(
                    batch,
                    on_conflict="prediction_id,rule_id",
                    ignore_duplicates=True,
                )
                .execute()
            )
        except Exception as exc:
            _log_database_error("recommendation_upsert", exc)
            failed_count += len(batch)
            continue

        expected = {
            _recommendation_key(record): record
            for record in batch
        }
        prediction_ids = list(
            dict.fromkeys(record["prediction_id"] for record in batch)
        )
        rule_ids = list(dict.fromkeys(record["rule_id"] for record in batch))

        # Keep the readback query compatible with the repository's batch
        # query contract, then validate each exact (prediction_id, rule_id).
        try:
            response = (
                client.table("recommendations")
                .select(RECOMMENDATION_READBACK_COLUMNS)
                .in_("prediction_id", prediction_ids)
                .in_("rule_id", rule_ids)
                .eq("learners.dataset_id", dataset_id)
                .execute()
            )
        except Exception as exc:
            _log_database_error("recommendation_readback", exc)
            failed_count += len(batch)
            continue

        matches: dict[tuple[str, str], dict] = {}
        invalid_readback: set[tuple[str, str]] = set()

        for row in response.data or []:
            if not isinstance(row, dict):
                continue

            prediction_id = row.get("prediction_id")
            rule_id = row.get("rule_id")

            if not isinstance(prediction_id, str) or not isinstance(rule_id, str):
                continue

            key = (prediction_id, rule_id)
            candidate = expected.get(key)

            # Rows returned by the two IN filters may include combinations
            # not present in the input batch. Ignore those unrelated rows.
            if candidate is None:
                continue

            learner = row.get("learners")
            if (
                row.get("learner_id") != candidate["learner_id"]
                or not isinstance(learner, dict)
                or learner.get("id") != candidate["learner_id"]
                or str(learner.get("dataset_id")) != str(dataset_id)
            ):
                invalid_readback.add(key)
                matches.pop(key, None)
                continue

            if key in matches:
                invalid_readback.add(key)
                matches.pop(key, None)
                continue

            matches[key] = {
                field: value
                for field, value in row.items()
                if field != "learners"
            }

        for key in expected:
            if key in invalid_readback:
                failed_count += 1
                continue

            saved = matches.get(key)
            if saved is None:
                failed_count += 1
                continue

            persisted.append(saved)

    logger.info(
        "Recommendation persistence finished "
        "(input=%d, valid_unique=%d, persisted=%d, failed=%d)",
        len(records),
        len(candidates),
        len(persisted),
        failed_count,
    )

    return {"persisted": persisted, "failed_count": failed_count}


def get_dashboard_summary(dataset_id: str):
    response = (
        _client()
        .table("dataset_dashboard_summary")
        .select("*")
        .eq("dataset_id", dataset_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None
