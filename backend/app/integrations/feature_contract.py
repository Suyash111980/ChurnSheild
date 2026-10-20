"""Load the versioned ML input schema shared with backend upload validation."""

import json
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FEATURE_SCHEMA_PATH = PROJECT_ROOT / "ml" / "schemas" / "oulad-learner-v1.json"


@lru_cache(maxsize=1)
def load_feature_contract() -> dict:
    try:
        contract = json.loads(FEATURE_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Canonical ML feature schema is unavailable") from exc
    features = contract.get("categorical_features", []) + contract.get("numeric_features", [])
    if not features or len(features) != len(set(features)):
        raise RuntimeError("Canonical ML feature schema is invalid")
    return contract


def feature_columns() -> list[str]:
    contract = load_feature_contract()
    return contract["categorical_features"] + contract["numeric_features"]


def numeric_feature_columns() -> list[str]:
    return list(load_feature_contract()["numeric_features"])
