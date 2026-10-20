"""Dataset-scoped descriptive and persisted-prediction dashboard contract."""

from typing import Any

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    dataset_id: str
    total_learner_records: int
    course_presentation_count: int
    learners_with_prediction: int
    prediction_coverage: float | None
    risk_distribution: dict[str, int] | None
    prediction_state: str
    descriptive_statistics: dict[str, Any]
