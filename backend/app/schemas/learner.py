"""Learner list and profile response contracts."""

from typing import Any

from pydantic import BaseModel


class LearnerPage(BaseModel):
    data: list[dict[str, Any]]
    limit: int
    offset: int
    count: int
    total: int
    has_more: bool


class LearnerProfile(BaseModel):
    learner: dict[str, Any]
    student_name: str | None
    latest_feature_snapshot: dict[str, Any] | None
    latest_prediction: dict[str, Any] | None
    risk_explanations: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
