"""Dataset-scoped descriptive and persisted-prediction dashboard contract."""

from typing import Any

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    dataset_id: str
    scope: str = "dataset"
    dataset_count: int = 1
    dataset_comparison: list[dict[str, Any]] = Field(default_factory=list)
    total_learner_records: int
    course_presentation_count: int
    learners_with_prediction: int
    prediction_coverage: float | None
    risk_distribution: dict[str, int] | None
    prediction_state: str
    descriptive_statistics: dict[str, Any]


class CourseInsight(BaseModel):
    code_module: str
    code_presentation: str
    learner_course_records: int
    learners_with_prediction: int
    prediction_coverage: float | None
    low_risk_count: int
    medium_risk_count: int
    high_risk_count: int
    average_risk_probability: float | None


class CourseInsights(BaseModel):
    dataset_id: str
    learner_course_records: int
    course_presentation_count: int
    learners_with_prediction: int
    courses: list[CourseInsight]
    weekly_activity_available: bool
