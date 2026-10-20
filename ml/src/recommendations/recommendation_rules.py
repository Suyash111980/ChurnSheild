"""Conservative, evidence-linked suggestions for human review.

These rules do not interpret model probability, assert a cause, or trigger an
intervention. The evidence fields come from the day-30 feature contract.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ml.src.features.build_features import validate_feature_frame


def recommend_for_records(records: pd.DataFrame | list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Return zero or more review suggestions for each validated feature row."""
    features = validate_feature_frame(records)
    results: list[list[dict[str, Any]]] = []
    for _, row in features.iterrows():
        suggestions: list[dict[str, Any]] = []
        no_activity = row["vle_has_activity_by_cutoff"]
        if pd.notna(no_activity) and float(no_activity) == 0:
            suggestions.append({
                "rule_id": "no_observed_vle_activity_by_cutoff",
                "action": "Check the learner's platform access and offer a supportive check-in.",
                "evidence": {
                    "feature": "vle_has_activity_by_cutoff",
                    "observed_value": 0,
                    "interpretation": "No VLE activity was recorded by the feature cutoff; this may also reflect missing logging.",
                },
                "requires_human_review": True,
            })

        no_submission = row["assessments_without_submission_recorded_by_cutoff"]
        if pd.notna(no_submission) and float(no_submission) > 0:
            suggestions.append({
                "rule_id": "assessment_without_submission_recorded_by_cutoff",
                "action": "Check whether assessment guidance or support would be useful.",
                "evidence": {
                    "feature": "assessments_without_submission_recorded_by_cutoff",
                    "observed_value": int(no_submission),
                    "interpretation": "A due assessment had no submission recorded by the cutoff; this is not proof of a missed assessment.",
                },
                "requires_human_review": True,
            })
        results.append(suggestions)
    return results
