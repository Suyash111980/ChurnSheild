"""Persisted prediction read response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PredictionPage(BaseModel):
    data: list[dict[str, Any]]
    limit: int
    offset: int
    count: int
    total: int
    has_more: bool


class RiskExplanation(BaseModel):
    id: str
    prediction_id: str
    feature_name: str
    feature_value: Any = None
    contribution: float
    created_at: datetime | None = None


class ExplanationList(BaseModel):
    data: list[RiskExplanation]
    prediction_id: str
