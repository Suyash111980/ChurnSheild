"""Translate withdrawal probability using the shared provisional risk bands."""

import json
from pathlib import Path

_CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "schemas" / "oulad-learner-v1.json").read_text(encoding="utf-8")
)
LOW_MAX_EXCLUSIVE = float(_CONTRACT["risk_bands"]["low_max_exclusive"])
HIGH_MIN_INCLUSIVE = float(_CONTRACT["risk_bands"]["high_min_inclusive"])


def risk_category(probability: float) -> str:
    value = float(probability)
    if not 0.0 <= value <= 1.0:
        raise ValueError("Risk probability must be between zero and one")
    if value < LOW_MAX_EXCLUSIVE:
        return "low"
    if value < HIGH_MIN_INCLUSIVE:
        return "medium"
    return "high"
