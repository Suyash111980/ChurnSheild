"""Recommendation read and status-update response contracts."""

from typing import Any, Literal

from pydantic import BaseModel


class RecommendationPage(BaseModel):
    data: list[dict[str, Any]]
    limit: int
    offset: int
    count: int
    total: int
    has_more: bool


class RecommendationStatusUpdate(BaseModel):
    status: Literal["in_progress", "completed", "dismissed"]


class EarlyWarningPage(BaseModel):
    data: list[dict[str, Any]]
    limit: int
    offset: int
    count: int
    total: int
    has_more: bool
