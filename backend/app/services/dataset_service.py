
"""Owner-checked dataset workflow and bounded canonical-row persistence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
import math
import re
import traceback
from numbers import Real
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd

from app.integrations.feature_contract import feature_columns
from app.integrations.ml_loader import (
    ModelArtifactError,
    ModelFeatureError,
    explain_records,
    predict_records,
    recommend_records,
)
from app.repositories import dataset_repository
from app.schemas.dataset import DatasetPage
from app.utils.dataset_parser import DatasetUploadError, ParsedDataset, parse_dataset

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = feature_columns()
BATCH_SIZE = 250
MAX_PREDICTION_ROWS = 10_000
EVIDENCE_BATCH_SIZE = 10
LEARNER_FIELDS = (
    "gender", "region", "highest_education", "imd_band", "age_band",
    "num_of_prev_attempts", "studied_credits", "disability",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_value(value: Any):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def _source_key(row: dict) -> tuple[str, str, str]:
    source_id = row.get("external_learner_id", row.get("id_student"))
    return (
        str(source_id).strip(),
        str(row["code_module"]).strip(),
        str(row["code_presentation"]).strip(),
    )


def _source_keys(frame: pd.DataFrame) -> set[tuple[str, str, str]]:
    return {_source_key(row) for row in frame.to_dict(orient="records")}


def _source_fingerprint(frame: pd.DataFrame) -> str:
    """Hash normalized parsed content so replacements cannot expose stale rows."""
    serialized = frame.to_csv(index=False, header=True, na_rep="<NA>", lineterminator="\n")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _learner_payload(row: dict, dataset_id: str) -> dict:
    payload = {
        "dataset_id": dataset_id,
        "external_learner_id": str(row["id_student"]).strip(),
        "code_module": str(row["code_module"]).strip(),
        "code_presentation": str(row["code_presentation"]).strip(),
        "updated_at": _utc_now(),
    }
    for column in LEARNER_FIELDS:
        if column not in row:
            continue
        value = _safe_value(row[column])
        if column in {"num_of_prev_attempts", "studied_credits"} and value is not None:
            value = int(value)
        if column == "disability":
            normalized = str(value).strip().upper() if value is not None else ""
            value = (
                True if normalized in {"Y", "TRUE", "1"}
                else False if normalized in {"N", "FALSE", "0"}
                else None
            )
        payload[column] = value
    return payload


def _feature_payload(row: dict, learner_id: str, as_of_date: str) -> dict:
    return {
        "learner_id": learner_id,
        "as_of_date": as_of_date,
        "features": {
            name: _safe_value(row.get(name))
            for name in FEATURE_COLUMNS
            if name in row
        },
    }


def _explanation_rows_match(payload: list[dict], saved: Any) -> bool:
    """Confirm the repository returned exactly the explanation keys we wrote."""
    if not isinstance(saved, list) or len(saved) != len(payload):
        return False

    expected = {
        (str(row.get("prediction_id")), row.get("feature_name"))
        for row in payload
    }
    returned = []
    for row in saved:
        if not isinstance(row, dict):
            return False
        prediction_id = row.get("prediction_id")
        feature_name = row.get("feature_name")
        if not isinstance(prediction_id, str) or not isinstance(feature_name, str):
            return False
        returned.append((prediction_id, feature_name))

    return (
        len(expected) == len(payload)
        and len(set(returned)) == len(returned)
        and set(returned) == expected
    )


def _persist_prediction_evidence(
    *,
    dataset_id: str,
    feature_records: list[dict],
    learner_ids: list[str],
    model_versions: list[str],
    saved_predictions: list[dict],
) -> dict:
    """Persist validated auxiliary evidence linked to exact saved predictions."""
    verified_predictions = []

    for learner_id, version in zip(learner_ids, model_versions, strict=True):
        matches = [
            row for row in saved_predictions
            if str(row.get("learner_id")) == str(learner_id)
            and str(row.get("model_version")) == str(version)
            and row.get("id")
        ]
        verified_predictions.append(matches[0] if len(matches) == 1 else None)

    result = {
        "explanations_state": "unavailable",
        "explanations_persisted": 0,
        "explanations_failed": 0,
        "recommendations_state": "unavailable",
        "recommendations_persisted": 0,
        "recommendations_failed": 0,
    }

    valid_indices = [
        index
        for index, row in enumerate(verified_predictions)
        if row is not None
    ]
    invalid_associations = len(verified_predictions) - len(valid_indices)

    if not valid_indices:
        if verified_predictions:
            result["explanations_state"] = "unavailable"
            result["explanations_failed"] = invalid_associations
            result["recommendations_state"] = "unavailable"
            result["recommendations_failed"] = invalid_associations
        else:
            result["explanations_state"] = "not_applicable"
            result["recommendations_state"] = "not_applicable"
        return result

    result["explanations_failed"] += invalid_associations
    result["recommendations_failed"] += invalid_associations

    eligible_features = [feature_records[index] for index in valid_indices]

    # ---------------------------------------------------------
    # Explanation generation and persistence
    # ---------------------------------------------------------
    try:
        explanations = explain_records(eligible_features)
        if (
            not isinstance(explanations, list)
            or len(explanations) != len(valid_indices)
        ):
            raise ValueError("explanation row count mismatch")
    except Exception as exc:
        logger.exception(
            "Explanation generation failed (exception_type=%s)",
            type(exc).__name__,
        )
        explanations = None

    if explanations is None:
        result["explanations_failed"] = len(valid_indices)

    if explanations is not None:
        learner_payloads = []

        for index, contributions in zip(
            valid_indices, explanations, strict=True
        ):
            if not isinstance(contributions, list):
                result["explanations_failed"] += 1
                continue

            seen = set()
            contribution_by_feature = {}
            valid = True

            for item in contributions:
                if not isinstance(item, dict):
                    valid = False
                    break

                name = item.get("feature_name")
                value = item.get("contribution")

                if not isinstance(value, Real) or isinstance(value, bool):
                    valid = False
                    break

                contribution = float(value)

                if (
                    name not in FEATURE_COLUMNS
                    or name in seen
                    or not math.isfinite(contribution)
                ):
                    valid = False
                    break

                seen.add(name)
                contribution_by_feature[name] = contribution

            if not valid or seen != set(FEATURE_COLUMNS):
                result["explanations_failed"] += 1
                continue

            row = verified_predictions[index]
            learner_payloads.append([
                {
                    "prediction_id": str(row["id"]),
                    "feature_name": name,
                    "feature_value": _safe_value(
                        feature_records[index].get(name)
                    ),
                    "contribution": contribution_by_feature[name],
                }
                for name in FEATURE_COLUMNS
            ])

        for offset in range(0, len(learner_payloads), EVIDENCE_BATCH_SIZE):
            group = learner_payloads[offset:offset + EVIDENCE_BATCH_SIZE]
            payload = [
                item
                for learner_rows in group
                for item in learner_rows
            ]

            try:
                saved = dataset_repository.upsert_explanations(payload)

                if not _explanation_rows_match(payload, saved):
                    result["explanations_failed"] += len(group)
                    logger.warning(
                        "Explanation persistence verification failed "
                        "(group_size=%d)",
                        len(group),
                    )
                else:
                    result["explanations_persisted"] += len(saved)

            except Exception as exc:
                logger.exception(
                    "Explanation persistence failed "
                    "(exception_type=%s, group_size=%d)",
                    type(exc).__name__,
                    len(group),
                )
                result["explanations_failed"] += len(group)

    result["explanations_state"] = (
        "available"
        if result["explanations_persisted"] and not result["explanations_failed"]
        else "partial"
        if result["explanations_persisted"]
        else "unavailable"
    )

    # ---------------------------------------------------------
    # Recommendation generation
    # ---------------------------------------------------------
    logger.info(
        "Recommendation generation starting (eligible_records=%d)",
        len(eligible_features),
    )

    try:
        suggestions = recommend_records(eligible_features)

        if (
            not isinstance(suggestions, list)
            or len(suggestions) != len(valid_indices)
        ):
            raise ValueError("recommendation row count mismatch")

        total_suggestions = sum(
            len(row) for row in suggestions if isinstance(row, list)
        )

        logger.info(
            "Recommendation generation completed "
            "(eligible_records=%d, suggestion_rows=%d, total_suggestions=%d)",
            len(eligible_features),
            len(suggestions),
            total_suggestions,
        )

    except Exception as exc:
        logger.exception(
            "Recommendation generation failed (exception_type=%s)",
            type(exc).__name__,
        )
        suggestions = None

    if suggestions is None:
        result["recommendations_failed"] = len(valid_indices)

        logger.warning(
            "Recommendation generation unavailable (eligible_records=%d)",
            len(valid_indices),
        )

    if suggestions is not None:
        recommendation_payload = []
        rejected_count = 0
        empty_suggestion_rows = 0

        for index, row_suggestions in zip(
            valid_indices, suggestions, strict=True
        ):
            if not isinstance(row_suggestions, list):
                result["recommendations_failed"] += 1
                rejected_count += 1
                continue

            if not row_suggestions:
                empty_suggestion_rows += 1

            row = verified_predictions[index]

            for suggestion in row_suggestions:
                if not isinstance(suggestion, dict):
                    result["recommendations_failed"] += 1
                    rejected_count += 1
                    continue

                rule_id = suggestion.get("rule_id")
                action = suggestion.get("action")

                expected_learner_id = str(learner_ids[index])
                expected_prediction_id = str(row["id"])

                evidence = suggestion.get("evidence")
                feature_name = (
                    evidence.get("feature")
                    if isinstance(evidence, dict)
                    else None
                )
                observed_value = (
                    _safe_value(evidence.get("observed_value"))
                    if isinstance(evidence, dict)
                    else None
                )
                interpretation = (
                    evidence.get("interpretation")
                    if isinstance(evidence, dict)
                    else None
                )

                if (
                    not isinstance(rule_id, str)
                    or not rule_id.strip()
                    or not isinstance(action, str)
                    or not action.strip()
                    or suggestion.get("learner_id", expected_learner_id)
                    != expected_learner_id
                    or suggestion.get("prediction_id", expected_prediction_id)
                    != expected_prediction_id
                    or not isinstance(feature_name, str)
                    or feature_name not in FEATURE_COLUMNS
                    or feature_name not in feature_records[index]
                    or observed_value is None
                    or observed_value
                    != _safe_value(feature_records[index].get(feature_name))
                    or not isinstance(interpretation, str)
                    or not interpretation.strip()
                    or suggestion.get("requires_human_review") is not True
                ):
                    result["recommendations_failed"] += 1
                    rejected_count += 1
                    continue

                reason = (
                    f"{rule_id}: {interpretation} "
                    f"(observed {feature_name}={observed_value!r})"
                )

                recommendation_payload.append({
                    "learner_id": expected_learner_id,
                    "prediction_id": expected_prediction_id,
                    "rule_id": rule_id.strip(),
                    "action": action,
                    "reason": reason,
                    "status": "pending",
                    "updated_at": _utc_now(),
                })

        logger.info(
            "Recommendation validation completed "
            "(eligible_records=%d, payload_count=%d, rejected_count=%d, "
            "empty_suggestion_rows=%d)",
            len(eligible_features),
            len(recommendation_payload),
            rejected_count,
            empty_suggestion_rows,
        )

        # -----------------------------------------------------
        # Recommendation persistence
        # -----------------------------------------------------
        if recommendation_payload:
            try:
                persistence = dataset_repository.upsert_recommendations(
                    recommendation_payload,
                    dataset_id=dataset_id,
                )

                persisted_rows = persistence.get("persisted", [])
                persistence_failed = persistence.get("failed_count", 0)

                result["recommendations_persisted"] = len(persisted_rows)
                result["recommendations_failed"] += persistence_failed

                logger.info(
                    "Recommendation persistence returned "
                    "(payload_count=%d, persisted=%d, failed=%d)",
                    len(recommendation_payload),
                    result["recommendations_persisted"],
                    persistence_failed,
                )

            except Exception as exc:
                logger.exception(
                    "Recommendation persistence failed "
                    "(exception_type=%s, payload_count=%d)",
                    type(exc).__name__,
                    len(recommendation_payload),
                )
                result["recommendations_failed"] += len(
                    recommendation_payload
                )
        else:
            logger.info(
                "Recommendation persistence skipped (reason=no_valid_candidates)"
            )

        result["recommendations_state"] = (
            "available"
            if (
                result["recommendations_persisted"]
                and not result["recommendations_failed"]
            )
            else "empty"
            if (
                not result["recommendations_failed"]
                and all(not row for row in suggestions)
            )
            else "partial"
            if result["recommendations_persisted"]
            else "unavailable"
        )

    logger.info(
        "Prediction evidence processing finished "
        "(eligible_records=%d, explanations_persisted=%d, "
        "explanations_failed=%d, recommendations_state=%s, "
        "recommendations_persisted=%d, recommendations_failed=%d)",
        len(eligible_features),
        result["explanations_persisted"],
        result["explanations_failed"],
        result["recommendations_state"],
        result["recommendations_persisted"],
        result["recommendations_failed"],
    )

    return result


def _metadata_payload(
    owner_id: str,
    workspace_id: str,
    dataset_name: str,
    filename: str,
    content_size: int,
) -> dict:
    safe_filename = Path(filename or "dataset.csv").name[:255]
    safe_name = (
        dataset_name or Path(safe_filename).stem or "Uploaded dataset"
    ).strip()[:120]

    return {
        "owner_id": owner_id,
        "workspace_id": workspace_id,
        "dataset_name": safe_name,
        "filename": safe_filename,
        "file_size_bytes": content_size,
        "status": "uploaded",
        "processing_progress": 0,
        "validation_results": {},
    }


def get_owned_dataset(
    dataset_id: str,
    owner_id: str,
    workspace_id: str,
) -> dict | None:
    return dataset_repository.get_owned_dataset(
        dataset_id, owner_id, workspace_id
    )


def list_owned_datasets(
    *,
    owner_id: str,
    workspace_id: str,
    limit: int,
    offset: int,
) -> dict:
    response = dataset_repository.list_owned_datasets(
        owner_id=owner_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )

    rows = response.data or []
    total = response.count if response.count is not None else len(rows)

    return {
        "data": rows,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "total": total,
        "has_more": offset + len(rows) < total,
    }


def preview_upload(filename: str, content: bytes) -> dict:
    parsed = parse_dataset(filename, content)

    return {
        "filename": Path(filename or "dataset.csv").name,
        "file_size_bytes": len(content),
        "row_count": int(len(parsed.frame)),
        "columns": list(parsed.frame.columns),
        "preview_rows": parsed.report.get("preview", []),
        "validation": parsed.report,
    }


def _record_failure(
    dataset_id: str,
    owner_id: str,
    workspace_id: str,
    report: dict,
    summary: str,
    *,
    processing_progress: int = 0,
) -> dict:
    updates = {
        "status": "failed",
        "processing_progress": processing_progress,
        "error_summary": summary,
        "validation_results": report,
        "updated_at": _utc_now(),
    }

    record = dataset_repository.update_owned_dataset(
        dataset_id, owner_id, workspace_id, updates
    )

    if record is None:
        raise RuntimeError("database_unavailable")

    return record


def _log_processing_event(dataset_id: str, stage: str, event: str, **fields) -> None:
    """Emit bounded, structured processing metadata without learner data."""
    details = " ".join(
        f"{key}={value}"
        for key, value in fields.items()
        if isinstance(value, (str, int, float, bool)) and value is not None
    )
    logger.info(
        "dataset_processing dataset_id=%s stage=%s event=%s%s",
        dataset_id,
        stage,
        event,
        f" {details}" if details else "",
    )


def _safe_error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and not isinstance(code, bool):
        code = str(code)
    if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", code):
        return code
    return "unavailable"


def _log_processing_exception(dataset_id: str, stage: str, exc: Exception) -> None:
    # Log the traceback frames and safe exception metadata, but not the raw
    # provider exception message (which can contain request or row details).
    stack = "".join(traceback.format_tb(exc.__traceback__))
    logger.error(
        "dataset_processing dataset_id=%s stage=%s event=failed "
        "exception_type=%s provider_code=%s traceback_frames=%s",
        dataset_id,
        stage,
        type(exc).__name__,
        _safe_error_code(exc),
        stack.rstrip(),
    )


def _processing_failure_summary(stage: str, exc: Exception) -> tuple[str, str, str]:
    """Map internal failures to safe, actionable user-facing diagnostics."""
    if isinstance(exc, ModelArtifactError):
        return (
            "model_unavailable",
            "The approved model could not be loaded. No predictions were saved; verify the deployed model artifact and retry.",
            "Model prediction could not run because the approved model artifact is unavailable.",
        )
    if isinstance(exc, ModelFeatureError):
        return (
            "model_feature_contract_failed",
            "The model could not process this dataset's features. No predictions were saved; verify the approved model and feature schema.",
            "Model prediction could not run because the feature contract was not satisfied.",
        )
    messages = {
        "learner_persistence": (
            "learner_persistence_failed",
            "Learner records could not be saved. Retry processing.",
            "Learner records were not fully saved, so prediction processing did not complete.",
        ),
        "feature_persistence": (
            "feature_persistence_failed",
            "Feature snapshots could not be saved. No predictions were confirmed; retry processing.",
            "Feature snapshot persistence failed before inference began.",
        ),
        "preprocessing_and_inference": (
            "prediction_inference_failed",
            "Model prediction could not be completed. Verify the approved model and feature contract, then retry.",
            "Prediction generation failed; no prediction result was confirmed.",
        ),
        "prediction_persistence": (
            "prediction_persistence_failed",
            "Predictions could not be saved and verified. Retry processing.",
            "Prediction persistence did not complete and verify successfully.",
        ),
        "explanation_and_recommendation_generation": (
            "evidence_processing_failed",
            "Saved predictions could not be fully finalized with their supporting evidence. Contact support before retrying.",
            "Prediction evidence finalization failed after inference.",
        ),
        "dataset_finalization": (
            "dataset_finalization_failed",
            "Processing results could not be finalized. Refresh the dataset status or contact support.",
            "The processing result could not be finalized.",
        ),
    }
    return messages.get(stage, (
        "dataset_processing_failed",
        "Dataset processing could not be completed. Retry processing or contact support.",
        "Dataset processing failed before a successful result was confirmed.",
    ))


def _update_dataset(
    dataset_id: str,
    owner_id: str,
    workspace_id: str,
    updates: dict,
) -> dict:
    record = dataset_repository.update_owned_dataset(
        dataset_id, owner_id, workspace_id, updates
    )

    if record is None:
        raise RuntimeError("dataset_update_missing")

    return record


def _process_parsed_dataset(
    *,
    dataset_id: str,
    owner_id: str,
    workspace_id: str,
    parsed: ParsedDataset,
    initial_record: dict,
) -> dict:
    report = dict(parsed.report)
    report["source_fingerprint"] = _source_fingerprint(parsed.frame)
    if report["errors"] or not report["descriptive_compatible"]:
        report["processing_state"] = "validation_failed"
        report["failed_stage"] = "validation"
        failed = _record_failure(
            dataset_id,
            owner_id,
            workspace_id,
            report,
            "Upload validation failed. Review the validation errors and retry.",
        )
        return {"data": failed, "validation": report}

    _update_dataset(
        dataset_id,
        owner_id,
        workspace_id,
        {
            "status": "validated",
            "row_count": report["row_count"],
            "descriptive_compatible": True,
            "prediction_compatible": report["prediction_compatible"],
            "validation_results": report,
            "updated_at": _utc_now(),
        },
    )

    _update_dataset(
        dataset_id,
        owner_id,
        workspace_id,
        {
            "status": "processing",
            "processing_progress": 5,
            "updated_at": _utc_now(),
        },
    )

    records = parsed.frame.to_dict(orient="records")
    key_to_learner: dict[tuple[str, str, str], str] = {}

    report["prediction_state"] = "not_started"
    report["predictions_persisted"] = 0
    report["processing_state"] = "processing"
    processing_stage = "learner_persistence"
    processing_progress = 5
    _log_processing_event(dataset_id, processing_stage, "started", rows=len(records))
    try:
        chunks = [
            records[index:index + BATCH_SIZE]
            for index in range(0, len(records), BATCH_SIZE)
        ]

        for batch_index, batch in enumerate(chunks):
            _log_processing_event(
                dataset_id, processing_stage, "batch_started",
                batch=batch_index + 1, batches=len(chunks), rows=len(batch),
            )
            upserted = dataset_repository.upsert_learners([
                _learner_payload(row, dataset_id)
                for row in batch
            ])

            for learner in upserted:
                if str(learner.get("dataset_id")) != str(dataset_id):
                    raise RuntimeError("learner_dataset_scope_mismatch")

                key_to_learner[_source_key(learner)] = str(learner["id"])

            if len(key_to_learner) < sum(
                len(chunk) for chunk in chunks[:batch_index + 1]
            ):
                raise RuntimeError("learner_rows_not_returned")

            progress = 10 + int(
                55 * (batch_index + 1) / max(len(chunks), 1)
            )
            processing_progress = progress

            _update_dataset(
                dataset_id,
                owner_id,
                workspace_id,
                {
                    "processing_progress": progress,
                    "updated_at": _utc_now(),
                },
            )
            _log_processing_event(
                dataset_id, processing_stage, "batch_completed",
                batch=batch_index + 1, batches=len(chunks),
                rows=len(key_to_learner), progress=progress,
            )

        if len(key_to_learner) != len(records):
            raise RuntimeError("learner_mapping_incomplete")
        _log_processing_event(
            dataset_id, processing_stage, "completed", rows=len(key_to_learner),
        )

        processing_stage = "feature_persistence"
        _log_processing_event(dataset_id, processing_stage, "started", rows=len(records))
        as_of_date = datetime.now(timezone.utc).date().isoformat()
        feature_batches = max(1, (len(records) + BATCH_SIZE - 1) // BATCH_SIZE)

        for batch_number, batch_index in enumerate(range(0, len(records), BATCH_SIZE), start=1):
            feature_rows = []

            for row in records[batch_index:batch_index + BATCH_SIZE]:
                learner_id = key_to_learner[_source_key(row)]
                feature_rows.append(
                    _feature_payload(row, learner_id, as_of_date)
                )

            _log_processing_event(
                dataset_id, processing_stage, "batch_started",
                batch=batch_number, batches=feature_batches, rows=len(feature_rows),
            )
            dataset_repository.upsert_features(feature_rows)
            processing_progress = 65 + int(15 * batch_number / feature_batches)
            _update_dataset(
                dataset_id,
                owner_id,
                workspace_id,
                {"processing_progress": processing_progress, "updated_at": _utc_now()},
            )
            _log_processing_event(
                dataset_id, processing_stage, "batch_completed",
                batch=batch_number, batches=feature_batches,
                rows=len(feature_rows), progress=processing_progress,
            )
        _log_processing_event(dataset_id, processing_stage, "completed", rows=len(records))

        prediction_state = "dataset_incompatible"
        prediction_count = 0
        saved_predictions: list[dict] = []
        inference_results: list[dict] = []
        feature_records: list[dict] = []
        ordered_ids: list[str] = []

        if (
            report["prediction_compatible"]
            and len(records) <= MAX_PREDICTION_ROWS
        ):
            prediction_state = "running"
            report["prediction_state"] = prediction_state
            processing_stage = "preprocessing_and_inference"
            _log_processing_event(dataset_id, processing_stage, "started", rows=len(records))
            feature_records = [
                {
                    column: _safe_value(row.get(column))
                    for column in FEATURE_COLUMNS
                }
                for row in records
            ]
            ordered_ids = [key_to_learner[_source_key(row)] for row in records]
            inference_results = predict_records(feature_records, record_ids=ordered_ids)
            if len(inference_results) != len(records):
                raise RuntimeError("prediction_result_count_mismatch")
            _log_processing_event(
                dataset_id, processing_stage, "completed", predictions=len(inference_results),
            )

            processing_stage = "prediction_persistence"
            _log_processing_event(dataset_id, processing_stage, "started", rows=len(inference_results))
            prediction_rows = [
                {
                    "learner_id": prediction["record_id"],
                    "model_version": prediction["model_version"],
                    "risk_probability": prediction["risk_probability"],
                    "risk_category": prediction["risk_category"],
                    "created_at": prediction["predicted_at"],
                }
                for prediction in inference_results
            ]

            saved_predictions = dataset_repository.upsert_predictions(prediction_rows)

            expected_keys = {
                (str(row["learner_id"]), str(row["model_version"]))
                for row in prediction_rows
            }
            saved_keys = {
                (str(row.get("learner_id")), str(row.get("model_version")))
                for row in saved_predictions
                if row.get("id") and row.get("learner_id") and row.get("model_version")
            }
            if len(saved_predictions) != len(prediction_rows) or saved_keys != expected_keys:
                raise RuntimeError("prediction_rows_not_returned")

            prediction_count = len(saved_predictions)
            prediction_state = "available"
            report["processing_state"] = "predictions_completed"
            processing_progress = max(processing_progress, 85)
            _update_dataset(
                dataset_id, owner_id, workspace_id,
                {"processing_progress": processing_progress, "updated_at": _utc_now()},
            )
            _log_processing_event(
                dataset_id, processing_stage, "completed", predictions=prediction_count,
            )
        elif report["prediction_compatible"]:
            prediction_state = "row_limit_exceeded"
            report["processing_state"] = "row_limit_exceeded"
            report["prediction_error_code"] = "prediction_row_limit_exceeded"
            report["prediction_message"] = (
                f"This dataset has {len(records):,} rows, above the configured prediction limit of "
                f"{MAX_PREDICTION_ROWS:,}. No predictions were run."
            )
        else:
            report["processing_state"] = "descriptive_only"
            missing = report.get("missing_prediction_columns") or []
            report["prediction_error_code"] = "required_features_missing"
            report["prediction_message"] = (
                "Learner records were saved for descriptive use, but predictions were not run because "
                "required model features are missing: " + ", ".join(missing)
            )

        report["prediction_state"] = prediction_state
        report["predictions_persisted"] = prediction_count
        report["prediction_rows_skipped"] = len(records) - prediction_count
        if prediction_state == "available":
            report["rows_cleaned_by_model_pipeline"] = report.get(
                "rows_with_recoverable_missing_values", 0
            )
            processing_stage = "explanation_and_recommendation_generation"
            _log_processing_event(dataset_id, processing_stage, "started", predictions=prediction_count)
            evidence = _persist_prediction_evidence(
                dataset_id=dataset_id,
                feature_records=feature_records,
                learner_ids=ordered_ids,
                model_versions=[
                    str(item["model_version"])
                    for item in inference_results
                ],
                saved_predictions=saved_predictions,
            )
            processing_progress = 95
            _update_dataset(
                dataset_id, owner_id, workspace_id,
                {"processing_progress": processing_progress, "updated_at": _utc_now()},
            )
            _log_processing_event(
                dataset_id,
                processing_stage,
                "completed",
                explanations=evidence.get("explanations_persisted", 0),
                recommendations=evidence.get("recommendations_persisted", 0),
            )
        else:
            evidence = {
                "explanations_state": "not_applicable",
                "explanations_persisted": 0,
                "recommendations_state": "not_applicable",
                "recommendations_persisted": 0,
            }

        report.update(evidence)
        if prediction_state == "available" and (
            evidence.get("explanations_state") in {"partial", "unavailable"}
            or evidence.get("recommendations_state") in {"partial", "unavailable"}
        ):
            report["processing_state"] = "predictions_completed_with_evidence_issues"
        processing_stage = "dataset_finalization"
        _log_processing_event(dataset_id, processing_stage, "started", rows=len(records))
        record = dataset_repository.update_owned_dataset(
            dataset_id,
            owner_id,
            workspace_id,
            {
                "status": "processed",
                "processing_progress": 100,
                "row_count": len(records),
                "processed_at": _utc_now(),
                "updated_at": _utc_now(),
                "error_summary": None,
                "validation_results": report,
            },
        )

        if record is None:
            raise RuntimeError("dataset_update_missing")

        _log_processing_event(
            dataset_id, processing_stage, "completed",
            prediction_state=report.get("prediction_state"),
            predictions=report.get("predictions_persisted", 0),
        )
        logger.info(
            "Dataset processing completed "
            "(prediction_state=%s, predictions_persisted=%d, "
            "recommendations_state=%s, recommendations_persisted=%d, "
            "recommendations_failed=%d)",
            report.get("prediction_state"),
            report.get("predictions_persisted", 0),
            report.get("recommendations_state", "not_applicable"),
            report.get("recommendations_persisted", 0),
            report.get("recommendations_failed", 0),
        )

        return {"data": record, "validation": report}

    except Exception as exc:
        _log_processing_exception(dataset_id, processing_stage, exc)
        report["processing_state"] = "failed"
        report["failed_stage"] = processing_stage
        error_code, safe_summary, prediction_message = _processing_failure_summary(processing_stage, exc)
        if report.get("prediction_state") == "running" or processing_stage in {
            "feature_persistence", "preprocessing_and_inference", "prediction_persistence"
        }:
            report["prediction_state"] = "failed"
            report["prediction_error_code"] = error_code
            report["prediction_message"] = prediction_message
            report["prediction_error"] = prediction_message

        try:
            record = _record_failure(
                dataset_id,
                owner_id,
                workspace_id,
                report,
                safe_summary,
                processing_progress=processing_progress,
            )
            return {"data": record, "validation": report}

        except Exception as failure_exc:
            _log_processing_exception(dataset_id, "failure_recording", failure_exc)
            raise RuntimeError("database_unavailable") from exc


def upload_dataset(
    *,
    owner_id: str,
    workspace_id: str,
    filename: str,
    dataset_name: str,
    content: bytes,
    dataset_id: str | None = None,
    allow_reprocess: bool = False,
) -> dict:
    existing_record = None
    if dataset_id is None:
        initial_record = dataset_repository.create_dataset(
            _metadata_payload(
                owner_id,
                workspace_id,
                dataset_name,
                filename,
                len(content),
            )
        )

        if initial_record is None:
            raise RuntimeError("database_unavailable")

        dataset_id = str(initial_record["id"])

    else:
        initial_record = get_owned_dataset(
            dataset_id, owner_id, workspace_id
        )

        if initial_record is None:
            return {"data": None, "validation": None}
        existing_record = initial_record
        allowed_statuses = {"failed"}

        if allow_reprocess:
            allowed_statuses.add("processed")

        if initial_record.get("status") not in allowed_statuses:
            raise ValueError("dataset_not_retryable")

    try:
        parsed = parse_dataset(filename, content)

    except DatasetUploadError as exc:
        if existing_record is not None:
            # Keep the previous processed revision available when a replacement
            # file is malformed; never hide valid saved results on a bad retry.
            raise ValueError("The replacement file failed validation; the existing dataset was preserved.") from exc
        report = {
            "errors": [{
                "code": "file_validation_failed",
                "message": str(exc),
            }],
            "warnings": [],
            "descriptive_compatible": False,
            "prediction_compatible": False,
            "row_count": None,
        }
        return {"data": _record_failure(
            dataset_id, owner_id, workspace_id, report,
            "Upload validation failed. Review the file format and size, then retry.",
        ), "validation": report}
    except Exception as exc:
        logger.warning("Dataset parsing failed (exception_type=%s)", type(exc).__name__)
        if existing_record is not None:
            raise ValueError("The replacement file could not be validated; the existing dataset was preserved.")
        report = {
            "errors": [{
                "code": "file_validation_failed",
                "message": "File validation could not be completed",
            }],
            "warnings": [],
            "descriptive_compatible": False,
            "prediction_compatible": False,
            "row_count": None,
        }

        return {
            "data": _record_failure(
                dataset_id,
                owner_id,
                workspace_id,
                report,
                "Upload validation failed. Review the file format and size, then retry.",
            ),
            "validation": report,
        }

    source_fingerprint = _source_fingerprint(parsed.frame)
    if existing_record is not None:
        previous_report = existing_record.get("validation_results") or {}
        previous_fingerprint = previous_report.get("source_fingerprint")
        if previous_fingerprint != source_fingerprint:
            # Enrichment can be safely applied in place only when the complete
            # learner-course membership is identical. Any membership change
            # gets a new dataset revision because this schema has no upload-run
            # key with which to distinguish stale rows.
            previous_keys = dataset_repository.get_dataset_source_keys(dataset_id)
            incoming_keys = _source_keys(parsed.frame)
            if previous_keys == incoming_keys:
                created_revision = False
                _update_dataset(
                    dataset_id,
                    owner_id, workspace_id,
                    {
                        "filename": Path(filename or "dataset.csv").name[:255],
                        "file_size_bytes": len(content),
                        "status": "uploaded",
                        "processing_progress": 0,
                        "error_summary": None,
                        "updated_at": _utc_now(),
                    },
                )
            else:
                base_name = str(existing_record.get("dataset_name") or "Uploaded dataset")
                revised_name = f"{base_name[:110]} (updated)"
                initial_record = dataset_repository.create_dataset(
                    _metadata_payload(owner_id, workspace_id, revised_name, filename, len(content))
                )
                if initial_record is None:
                    raise RuntimeError("database_unavailable")
                dataset_id = str(initial_record["id"])
                created_revision = True
        else:
            created_revision = False
            _update_dataset(
                dataset_id,
                owner_id, workspace_id,
                {
                    "filename": Path(filename or "dataset.csv").name[:255],
                    "file_size_bytes": len(content),
                    "status": "uploaded",
                    "processing_progress": 0,
                    "error_summary": None,
                    "updated_at": _utc_now(),
                },
            )
    else:
        created_revision = False

    result = _process_parsed_dataset(
        dataset_id=dataset_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        parsed=parsed,
        initial_record=initial_record,
    )
    if created_revision and result.get("validation") is not None:
        result["validation"]["source_revision_created"] = True
    return result
