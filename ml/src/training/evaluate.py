"""Metrics for the binary withdrawal baseline; positive class is Withdrawn=1."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_probabilities(y_true, probabilities, *, threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if y_true.shape != probabilities.shape or y_true.ndim != 1:
        raise ValueError("Labels and probabilities must be matching one-dimensional arrays")
    if not len(y_true) or not np.isin(y_true, [0, 1]).all():
        raise ValueError("Labels must be a non-empty binary array containing only 0 and 1")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Probabilities must be finite values between zero and one")
    if not 0 < threshold < 1:
        raise ValueError("Decision threshold must be strictly between zero and one")
    predicted = probabilities >= threshold
    matrix = confusion_matrix(y_true, predicted, labels=[0, 1])
    calibration_bins = []
    # Integer bin indices avoid floating-point boundary gaps (e.g. 0.6
    # comparing below a computed 0.6000000000000001 lower bound).
    bin_indices = np.minimum(np.floor(probabilities * 10).astype(int), 9)
    for index in range(10):
        lower = index / 10
        upper = (index + 1) / 10
        in_bin = bin_indices == index
        if in_bin.any():
            calibration_bins.append({
                "lower_bound_inclusive": round(float(lower), 1),
                "upper_bound_inclusive": round(float(upper), 1),
                "count": int(in_bin.sum()),
                "mean_predicted_probability": float(probabilities[in_bin].mean()),
                "observed_positive_rate": float(y_true[in_bin].mean()),
            })
    expected_calibration_error = float(sum(
        item["count"] / len(y_true)
        * abs(item["mean_predicted_probability"] - item["observed_positive_rate"])
        for item in calibration_bins
    ))
    return {
        "positive_class": "target_withdrawn=1 (Withdrawn)",
        "averaging": "binary; positive label 1",
        "decision_threshold": float(threshold),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)) if len(np.unique(y_true)) == 2 else None,
        "pr_auc_average_precision": float(average_precision_score(y_true, probabilities)),
        "positive_prevalence": float(y_true.mean()),
        "false_negatives": int(matrix[1, 0]),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "log_loss": float(log_loss(y_true, probabilities, labels=[0, 1])),
        "expected_calibration_error_equal_width_10_bins": expected_calibration_error,
        "calibration_bins_equal_width_0_1": calibration_bins,
        "confusion_matrix": {
            "labels": [0, 1],
            "rows_actual_columns_predicted": matrix.tolist(),
        },
        "class_distribution": {
            "0": int((y_true == 0).sum()),
            "1": int((y_true == 1).sum()),
        },
        "record_count": int(len(y_true)),
    }
