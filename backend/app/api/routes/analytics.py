"""Expose only saved, genuine held-out evaluation reports."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import require_roles
from app.core.config import settings

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/model-evaluation")
def model_evaluation(
    _user: dict[str, Any] = Depends(
        require_roles("master_admin")
    ),
):
    artifact = settings.resolve_backend_path(settings.model_path)
    evaluation_path = artifact.with_suffix(".evaluation.json")
    metadata_path = artifact.with_suffix(".metadata.json")
    try:
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No saved model evaluation is available.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Saved model evaluation is unreadable.") from exc
    if not isinstance(evaluation.get("test"), dict) or not metadata.get("model_version"):
        raise HTTPException(status_code=503, detail="Saved model evaluation is invalid.")
    return {
        "metric_scope": "held_out_grouped_test",
        "model_version": metadata["model_version"],
        "schema_version": metadata.get("schema_version"),
        "target": metadata.get("target"),
        "positive_class": metadata.get("positive_class"),
        "split": metadata.get("split"),
        "evaluation": evaluation,
        "limitations": metadata.get("limitations", []),
        "risk_bands": metadata.get("risk_bands"),
    }
