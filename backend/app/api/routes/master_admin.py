"""Platform-level metadata visible only to the configured Master Admin."""

import json
import logging
import re
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.integrations.feature_contract import feature_columns
from app.integrations.ml_loader import (
    ModelArtifactError,
    ModelFeatureError,
    get_model,
    predict_records,
    validate_model_features,
)
from app.integrations.supabase_client import supabase

router = APIRouter(prefix="/api/v1/master-admin", tags=["Master Admin"])
logger = logging.getLogger(__name__)


def _log_platform_query_failure(table: str, exc: Exception) -> None:
    code = getattr(exc, "code", None)
    safe_code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", code) else "unknown"
    logger.error(
        "Master Admin overview query failed (table=%s exception_type=%s provider_code=%s)",
        table,
        type(exc).__name__,
        safe_code,
    )


@router.get("/overview")
def platform_overview(_master: dict[str, Any] = Depends(require_roles("master_admin"))):
    if supabase is None:
        logger.error("Master Admin overview unavailable: server database client is not configured")
        raise HTTPException(status_code=503, detail="Platform data service is not configured.")
    rows = {}
    for table, columns in (
        ("profiles", "id, role, requested_role, approval_status"),
        ("workspaces", "id, status, admin_user_id"),
        ("dataset_uploads", "id, workspace_id, status"),
    ):
        try:
            rows[table] = supabase.table(table).select(columns).execute().data or []
        except Exception as exc:
            _log_platform_query_failure(table, exc)
            raise HTTPException(
                status_code=503,
                detail="Platform overview cannot read required database metadata. Verify deployed migrations and backend database permissions.",
            ) from exc
    profiles = rows["profiles"]
    workspaces = rows["workspaces"]
    datasets = rows["dataset_uploads"]
    master_id = settings.master_admin_user_id.strip().lower()
    requested = [p for p in profiles if p.get("requested_role") == "admin"]
    approved_admins = [p for p in profiles if p.get("role") == "admin" and p.get("approval_status") == "approved" and p.get("id", "").lower() != master_id]
    status_counts: dict[str, int] = {}
    for row in datasets:
        state = str(row.get("status") or "unknown")
        status_counts[state] = status_counts.get(state, 0) + 1
    return {
        "admin_accounts": len({p.get("id") for p in requested} | {p.get("id") for p in approved_admins}),
        "pending_admin_requests": sum(p.get("approval_status") == "pending" for p in requested),
        "approved_admins": len(approved_admins),
        "rejected_admins": sum(p.get("approval_status") == "denied" for p in requested),
        "workspaces": len(workspaces),
        "datasets": len(datasets),
        "dataset_status_counts": status_counts,
    }


@router.get("/oulad")
def oulad_overview(_master: dict[str, Any] = Depends(require_roles("master_admin"))):
    """Read local prepared reference data/artifact metadata; never imports it."""
    data_path = settings.resolve_backend_path("../ml/data/processed/oulad_learner_features.csv")
    artifact_path = settings.resolve_backend_path(settings.model_path)
    dataset: dict[str, Any] = {
        "name": "Open University Learning Analytics Dataset (OULAD)",
        "status": "not_available",
        "storage_scope": "local_reference_only",
        "storage_type": "local_csv",
        "storage_location": "ml/data/processed/oulad_learner_features.csv",
        "imported_to_supabase": False,
    }
    frame = None
    if data_path.is_file():
        try:
            frame = pd.read_csv(data_path)
            target_counts = {}
            if "target_withdrawn" in frame.columns:
                raw_counts = frame["target_withdrawn"].value_counts(dropna=False)
                target_counts = {str(key): int(value) for key, value in raw_counts.items()}
            learner_count = None
            if {"id_student", "code_module", "code_presentation"}.issubset(frame.columns):
                learner_count = int(frame[["id_student", "code_module", "code_presentation"]].drop_duplicates().shape[0])
            dataset = {
                **dataset,
                "status": "prepared_locally_not_imported",
                "record_count": int(len(frame)),
                "learner_course_presentation_count": learner_count,
                "course_count": int(frame["code_module"].nunique()) if "code_module" in frame else None,
                "presentation_count": int(frame["code_presentation"].nunique()) if "code_presentation" in frame else None,
                "target_withdrawal_distribution": target_counts or None,
                "file_modified_at": pd.Timestamp(data_path.stat().st_mtime, unit="s", tz="UTC").isoformat(),
            }
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            raise HTTPException(status_code=503, detail="Prepared OULAD reference data is unreadable.") from exc

    metadata_path = artifact_path.with_suffix(".metadata.json")
    evaluation_path = artifact_path.with_suffix(".evaluation.json")
    model: dict[str, Any] = {
        "name": "Random Forest" if artifact_path.is_file() else None,
        "version": None,
        "artifact_available": artifact_path.is_file(),
        "artifact_load_status": "not_checked" if artifact_path.is_file() else "unavailable",
        "metadata_status": "not_available",
        "evaluation_available": False,
        "evaluation_status": "not_available",
        "evaluation": None,
        "metadata": None,
        "training": {
            "prepared_cohort_rows": None,
            "train_rows": None,
            "validation_rows": None,
            "test_rows": None,
            "training_date": None,
            "duration_seconds": None,
        },
        "feature_count": None,
        "feature_columns": None,
        "inference": {
            "status": "not_available",
            "persisted": False,
            "full_dataset_status": "not_generated",
            "full_dataset_persisted": False,
            "full_dataset_prediction_count": None,
        },
        "recommendations": {
            "generation_status": "not_implemented",
            "existing_records_status": "persisted_records_read_and_status_updates_supported",
        },
    }
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else None
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8")) if evaluation_path.is_file() else None
        if isinstance(metadata, dict):
            model["version"] = metadata.get("model_version")
            model["metadata"] = metadata
            model["metadata_status"] = "available"
            columns = metadata.get("feature_columns")
            if isinstance(columns, list):
                model["feature_columns"] = columns
                model["feature_count"] = len(columns)
            split = metadata.get("split")
            row_counts = split.get("row_counts") if isinstance(split, dict) else None
            cohort = metadata.get("prepared_cohort")
            model["training"] = {
                "prepared_cohort_rows": cohort.get("rows") if isinstance(cohort, dict) else None,
                "train_rows": row_counts.get("train") if isinstance(row_counts, dict) else None,
                "validation_rows": row_counts.get("validation") if isinstance(row_counts, dict) else None,
                "test_rows": row_counts.get("test") if isinstance(row_counts, dict) else None,
                "training_date": metadata.get("training_date"),
                "duration_seconds": metadata.get("training_duration_seconds"),
            }
        if isinstance(evaluation, dict):
            model["evaluation"] = evaluation.get("test")
            model["evaluation_available"] = isinstance(evaluation.get("test"), dict)
            model["evaluation_status"] = "available" if model["evaluation_available"] else "not_available"
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Saved OULAD model metadata is unreadable.") from exc

    if artifact_path.is_file():
        columns = model["feature_columns"] or feature_columns()
        try:
            loaded_model = get_model()
            validate_model_features(loaded_model, columns)
        except (ModelArtifactError, ModelFeatureError):
            model["artifact_load_status"] = "unavailable"
        else:
            model["artifact_load_status"] = "loaded"

    if frame is not None and artifact_path.is_file():
        columns = feature_columns()
        if not set(columns).issubset(frame.columns):
            model["inference"]["status"] = "input_schema_mismatch"
        elif not frame.empty:
            try:
                result = predict_records(
                    frame[columns].head(1),
                    record_ids=["master-admin-local-oulad-check"],
                )
            except (ModelArtifactError, ModelFeatureError):
                model["inference"]["status"] = "model_unavailable"
            else:
                if result:
                    model["inference"].update({
                        "status": "sample_scored",
                        "persisted": False,
                        "model_version": result[0]["model_version"],
                    })
    return {"dataset": dataset, "model": model}
