"""Metrics for binary withdrawal-risk models."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)


def evaluate_binary_model(model, features, labels, threshold: float = 0.5) -> dict:
    """Return metrics with withdrawn (label 1) as the positive class."""
    if not 0 <= threshold <= 1:
        raise ValueError("Decision threshold must be between 0 and 1")
    y_true = np.asarray(labels, dtype=int)
    probabilities = model.predict_proba(features)[:, 1]
    predictions = (probabilities >= threshold).astype(int)
    try:
        auc = float(roc_auc_score(y_true, probabilities))
    except ValueError:
        auc = None
    return {
        "precision": float(precision_score(y_true, predictions, pos_label=1, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, pos_label=1, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, pos_label=1, zero_division=0)),
        "roc_auc": auc,
        "threshold": float(threshold),
        "positive_class": 1,
        "confusion_matrix_labels_0_1": confusion_matrix(y_true, predictions, labels=[0, 1]).tolist(),
        "class_counts": {str(int(k)): int(v) for k, v in zip(*np.unique(y_true, return_counts=True))},
        "sample_count": int(len(y_true)),
    }
