"""Validate and score records with a saved versioned inference pipeline."""

from __future__ import annotations

import json
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.src.features.build_features import FEATURE_COLUMNS, SCHEMA_VERSION, validate_feature_frame
from ml.src.inference.risk_categories import risk_category


class InferenceContractError(ValueError):
    """Input or saved artifact does not conform to the canonical contract."""


def load_inference_artifact(path: str | Path):
    artifact = Path(path).expanduser().resolve()
    try:
        stat = artifact.stat()
        metadata_stat = artifact.with_suffix(".metadata.json").stat()
    except OSError as exc:
        raise InferenceContractError("Model artifact or metadata is missing or unreadable") from exc
    return _load_cached(
        str(artifact), stat.st_mtime_ns, stat.st_size,
        metadata_stat.st_mtime_ns, metadata_stat.st_size,
    )


@lru_cache(maxsize=4)
def _load_cached(
    artifact_path: str,
    artifact_mtime_ns: int,
    artifact_size: int,
    metadata_mtime_ns: int,
    metadata_size: int,
):
    del artifact_mtime_ns, artifact_size, metadata_mtime_ns, metadata_size
    artifact = Path(artifact_path)
    metadata_path = artifact.with_suffix(".metadata.json")
    try:
        model = joblib.load(artifact)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise InferenceContractError("Model artifact or metadata is missing or unreadable") from exc
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise InferenceContractError("Model feature schema version is incompatible")
    if metadata.get("feature_columns") != FEATURE_COLUMNS:
        raise InferenceContractError("Model feature ordering does not match the canonical schema")
    if not callable(getattr(model, "predict_proba", None)):
        raise InferenceContractError("Model artifact does not support probability inference")
    if list(getattr(model, "feature_names_in_", [])) != FEATURE_COLUMNS:
        raise InferenceContractError("Model artifact has incompatible input feature names")
    return model, metadata


def predict_records(
    records: pd.DataFrame | list[dict[str, Any]],
    *,
    record_ids: list[str],
    artifact_path: str | Path,
) -> list[dict[str, Any]]:
    if len(record_ids) != len(records):
        raise InferenceContractError("One caller-supplied record ID is required for each input row")
    if not record_ids or any(not isinstance(value, str) or not value.strip() for value in record_ids):
        raise InferenceContractError("Caller-supplied record IDs must be non-empty strings")
    try:
        features = validate_feature_frame(records)
    except (ValueError, TypeError) as exc:
        raise InferenceContractError(str(exc)) from exc
    model, metadata = load_inference_artifact(artifact_path)
    classes = list(model.classes_)
    if 1 not in classes:
        raise InferenceContractError("Model does not include the Withdrawn positive class")
    try:
        all_probabilities = np.asarray(model.predict_proba(features), dtype=float)
    except Exception as exc:
        raise InferenceContractError("Model failed to produce probabilities") from exc
    if (
        all_probabilities.ndim != 2
        or all_probabilities.shape != (len(record_ids), len(classes))
        or not np.isfinite(all_probabilities).all()
        or ((all_probabilities < 0) | (all_probabilities > 1)).any()
        or not np.allclose(all_probabilities.sum(axis=1), 1.0, atol=1e-6)
    ):
        raise InferenceContractError("Model returned invalid probabilities")
    probabilities = all_probabilities[:, classes.index(1)]
    now = datetime.now(timezone.utc).isoformat()
    output = []
    for record_id, probability in zip(record_ids, probabilities, strict=True):
        value = float(probability)
        if not 0 <= value <= 1:
            raise InferenceContractError("Model returned a probability outside [0, 1]")
        output.append({
            "record_id": record_id,
            "risk_probability": value,
            "risk_category": risk_category(value),
            "model_version": metadata["model_version"],
            "predicted_at": now,
        })
    return output
