"""Lazy bridge to the shared, versioned ML inference contract."""

from functools import lru_cache
import json
from pathlib import Path
import sys

import joblib

from app.core.config import settings


class ModelArtifactError(RuntimeError):
    """The configured artifact is missing, unreadable, or not a classifier."""


class ModelFeatureError(ValueError):
    """Input feature names or ordering do not match the trained artifact."""


def require_approved_model_version(path: Path | None = None) -> str:
    """Fail closed unless the artifact sidecar matches an explicitly approved version."""
    approved_version = settings.model_approved_version.strip()
    if not approved_version:
        raise ModelArtifactError("Model inference is disabled until a model version is approved.")

    artifact_path = path or settings.resolve_backend_path(settings.model_path)
    metadata_path = artifact_path.with_suffix(".metadata.json")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError("Configured model metadata is missing or unreadable.") from exc

    model_version = metadata.get("model_version") if isinstance(metadata, dict) else None
    if not isinstance(model_version, str) or model_version != approved_version:
        raise ModelArtifactError("Configured model version is not approved for inference.")
    return model_version


@lru_cache(maxsize=4)
def _load_model(path_string: str, modified_ns: int, file_size: int):
    del modified_ns, file_size  # Cache key changes when the configured artifact changes.
    path = Path(path_string)
    if not path.is_file():
        raise ModelArtifactError("Configured model artifact does not exist.")
    try:
        model = joblib.load(path)
    except Exception as exc:
        raise ModelArtifactError("Configured model artifact could not be loaded.") from exc

    if not callable(getattr(model, "predict_proba", None)):
        raise ModelArtifactError("Configured model does not provide predict_proba.")
    if not callable(getattr(model, "predict", None)):
        raise ModelArtifactError("Configured model does not provide predict.")
    return model


def get_model():
    """Load the configured artifact once per file version; never at startup."""
    path = settings.resolve_backend_path(settings.model_path)
    try:
        stat = path.stat()
    except OSError as exc:
        raise ModelArtifactError("Configured model artifact does not exist.") from exc
    return _load_model(str(path), stat.st_mtime_ns, stat.st_size)


def validate_model_features(model, feature_names: list[str]) -> None:
    """Validate names/order when available, otherwise validate input width."""
    if "student_name" in feature_names:
        raise ModelFeatureError("Display names cannot be model input features.")
    expected_names = getattr(model, "feature_names_in_", None)
    if expected_names is not None:
        expected = [str(name) for name in expected_names]
        if feature_names != expected:
            raise ModelFeatureError("Feature names or order do not match the model.")
        return

    expected_count = getattr(model, "n_features_in_", None)
    if expected_count is None or len(feature_names) != int(expected_count):
        raise ModelFeatureError("Model feature count cannot be validated.")


def predict_records(records, *, record_ids: list[str]):
    """Call the shared versioned ML inference contract from this monorepo."""
    require_approved_model_version()
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from ml.src.inference.predict import (
            InferenceContractError,
            predict_records as run_inference,
        )
    except ImportError as exc:
        raise ModelArtifactError("The shared ML inference package is unavailable.") from exc
    try:
        return run_inference(
            records,
            record_ids=record_ids,
            artifact_path=settings.resolve_backend_path(settings.model_path),
        )
    except InferenceContractError as exc:
        raise ModelFeatureError("The model artifact or feature contract is unavailable.") from exc


def explain_records(records):
    """Generate SHAP evidence only from the explicitly approved artifact."""
    require_approved_model_version()
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from ml.src.explainability.shap_explainer import explain_with_shap
    except ImportError as exc:
        raise ModelArtifactError("The shared ML explanation package is unavailable.") from exc
    return explain_with_shap(get_model(), records)


def recommend_records(records):
    """Apply the existing evidence rules to validated canonical feature rows."""
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from ml.src.recommendations.recommendation_rules import recommend_for_records
    except ImportError as exc:
        raise ModelArtifactError("The shared recommendation rules are unavailable.") from exc
    return recommend_for_records(records)
