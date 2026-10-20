# ChurnShield OULAD Random Forest baseline

## Intended use and prediction target

Development baseline for prioritizing human review of learner withdrawal risk. It is not a decision system and must not be the sole basis for high-impact decisions. The unit is a learner-course-presentation row. `target_withdrawn=1` means OULAD `final_result` is `Withdrawn`; Pass, Fail, and Distinction are 0. Features use the project's provisional day-30 cutoff. The target and identifiers are excluded from features.

## Data and input schema

The legacy artifact used the locally prepared `ml/data/processed/oulad_learner_features.csv` sample (6,776 rows, 6,000 unique learners). The canonical ordered input columns and types are defined in `ml/schemas/oulad-learner-v1.json`. A grouped train/validation/test split holds out `id_student` groups; no learner appears in more than one split. Preprocessing is fit only on the training partition. A timing audit found 1,111 of its 2,149 Withdrawn rows had `date_unregistration` on or before day 30. The metrics below therefore do not measure valid day-30 future-withdrawal performance.

## Legacy broad-cohort evaluation (not valid for day-30 warning)

Training command: `python -m ml.src.training.train --data ml/data/processed/oulad_learner_features.csv --artifact ml/artifacts/churn_model.joblib --seed 42`.

| Test metric | Value |
|---|---:|
| Test rows | 1,363 |
| Class counts (0 / Withdrawn=1) | 889 / 474 |
| Precision, binary positive class 1, threshold 0.50 | 0.8000 |
| Recall, binary positive class 1, threshold 0.50 | 0.5654 |
| F1, binary positive class 1, threshold 0.50 | 0.6625 |
| ROC-AUC | 0.8195 |
| PR-AUC (average precision) | 0.7596 |
| Confusion matrix, rows actual [0,1], columns predicted [0,1] | `[[822, 67], [206, 268]]` |

These results are from one random grouped holdout on the prepared development sample. They do not establish temporal, institutional, or population-level generalization. The 0.50 threshold is a baseline choice, not an approved intervention threshold. Risk categories use separate provisional cutoffs at 0.30 and 0.70.

The validation partition contains 1,356 rows (923 class 0, 433 Withdrawn). At threshold 0.50, validation precision is 0.8185, recall 0.5520, F1 0.6593, ROC-AUC 0.8026, and PR-AUC (average precision) 0.7354. Confusion matrix (actual rows [0,1], predicted columns [0,1]): `[[870, 53], [194, 239]]`. This validation set is not used to claim external generalization. A fresh local training run with seed 42 reproduced the saved test metrics above.

A training-only prevalence reference (`DummyClassifier(strategy="prior")`) predicts the training prevalence for every row. At the fixed 0.50 threshold it predicts class 0 for all held-out records: test ROC-AUC 0.5000, PR-AUC 0.3478, precision 0, recall 0, and F1 0; validation ROC-AUC 0.5000 and PR-AUC 0.3193 (precision, recall, and F1 are 0). The Random Forest improves ranking and identifies some positive cases over this simple reference on this split; these results alone do not establish practical suitability.

## Separate day-30 temporal experiment

The versioned candidate uses only records registered by day 30 and uses `date_unregistration > 30` to time positive Withdrawn labels. Its cohort contains 5,634 rows (4,620 negative, 1,014 positive); 1,100 early unregistrations, 23 Withdrawn labels with no dated withdrawal, and 19 rows without registration by day 30 are excluded. It trains on 2013B/2013J, validates on 2014B, and tests on 2014J while keeping learner groups disjoint across partitions.

On the final 2014J holdout (1,925 rows; 18.18% positive), the threshold-0.50 candidate scored precision 0.3947, recall 0.0429, F1 0.0773, ROC-AUC 0.6056, and PR-AUC 0.2599, with 335 false negatives out of 350 positives. Confusion matrix: `[[1552, 23], [335, 15]]`. The same-partition prevalence baseline scored ROC-AUC 0.5000, PR-AUC 0.1818, and 350 false negatives. The earlier forward fold (2014B test) had ROC-AUC 0.5752 and PR-AUC 0.2438, with 255 false negatives out of 261 positives. These results are weak and vary by presentation; the candidate is not ready for operational warning.

The candidate's final-test Brier score is 0.1492, log loss 0.4735, and 10-bin expected calibration error 0.0508. These are diagnostics, not proof of calibrated probabilities. Validation-only threshold sensitivity at 0.30 found 69/207 positives (138 false negatives) with 240 false positives, compared with 8 detected (199 false negatives) and 17 false positives at 0.50. No operational cost matrix or review capacity was approved, so the threshold was not changed. The temporal test uses a later presentation and disjoint learner IDs, but six course modules overlap train and test; it does not establish performance on unseen courses. Full metrics and split details are in [the day-30 audit](../ml/reports/day30_prediction_audit.md).

## Limitations and safeguards

- OULAD cohort construction and the day-30 target definition need domain-owner confirmation.
- The day-30 candidate has two forward checks on four OULAD presentations. Learner groups and presentations are disjoint across each split, while six course modules overlap train/test; this is not unseen-course validation. There is no external validation, calibration fitting, approved threshold selection, subgroup fairness review, or prospective evaluation.
- Demographic/protected fields are excluded from model inputs, but proxy effects remain possible.
- The ML package exposes best-effort SHAP explanations, grouped to canonical source features. These describe model contribution, not causation. The application upload workflow does not persist explanations.
- The ML package exposes conservative, evidence-linked review suggestions based only on observed VLE activity and recorded assessment signals. They are not persisted, are not generated from causal findings, and require human review.
- The standalone batch inference CLI scores only inputs matching the versioned feature schema and refuses to overwrite an existing output. It is an offline tool, not a backend/API integration.
- Human review is required before outreach or other action.

## Local artifacts

The legacy training run produced `ml/artifacts/churn_model.joblib` and sidecars. The separate experiment produced `ml/artifacts/churn_model_day30_candidate.joblib` and aggregate metrics in `ml/reports/day30_experiment_evaluation.json`; it is a weak research candidate and must not be operationalized. The legacy artifact was loaded and scored over all 6,776 prepared rows (risk bands: 4,153 low, 1,380 medium, 1,243 high); these are in-sample cohort counts, not evaluation metrics. The artifacts directory is git-ignored. No production deployment, live API, or database integration was tested.

## Offline monitoring and handoff

Before any operational use, an owner should confirm the target and cutoff, approve risk-band and action thresholds, and define subgroup fairness and calibration acceptance criteria. For each future offline scoring batch, retain an aggregate-only report containing the model/schema versions, input and scored row counts, rejected/incompatible row counts, missing-feature rates, prediction probability and risk-band distributions, and source dataset/version. Once outcomes mature, compare observed withdrawal rates and calibration by time period and relevant subgroups; investigate drift and fairness changes before updating the model. Do not set automated alert thresholds from this single development sample. The repository does not implement online telemetry, alerting, or outcome feedback collection.

For a reproducible retraining review, first rerun OULAD preparation with the documented source files, inclusive cutoff, sample seed, and feature schema. Train a new versioned candidate to a new non-existing artifact path, retain the grouped/temporal evaluation report, and compare it with the prevalence baseline and prior candidate before any model-card update. Run the ML test suite, load the artifact in a fresh process, verify schema compatibility, and batch-score a held-out compatible input. Keep previous artifacts and reports for comparison; do not promote a candidate based only on its random grouped split.
