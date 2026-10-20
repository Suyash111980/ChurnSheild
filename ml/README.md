# ChurnShield ML: OULAD pipeline

This ML area contains OULAD exploration and preparation, a versioned Random Forest baseline, isolated batch inference, offline SHAP explanations, and evidence-linked human-review suggestions. It does not connect to the application database or provide online monitoring. Frontend and backend code are outside this scope.

## Data setup

Obtain the dataset from [the official OULAD dataset page](https://analyse.kmi.open.ac.uk/open_dataset). Keep the original files where they are, or place copies/symlinks locally under `ml/data/raw/` with these exact names:

```text
ml/data/raw/
  assessments.csv
  courses.csv
  studentAssessment.csv
  studentInfo.csv
  studentRegistration.csv
  studentVle.csv
  vle.csv
```

Raw data and processed learner data are git-ignored. Do not commit learner-level records or generated feature tables. This repo's initial data was supplied outside the repository; the explorer can read it directly with `--data-dir`, so copying the large VLE file is unnecessary.

## Environment and run

Use the repository's existing Python environment and ML dependencies (Pandas and NumPy are already listed in `requirements.txt` alongside packages used by the broader ML project). From the repository root:

```powershell
python -m venv ml\.venv
ml\.venv\Scripts\Activate.ps1
python -m pip install -r ml\requirements.txt
python ml\src\explore_oulad.py --data-dir "D:\my files\anonymisedData"
```

The script requires all seven CSVs and gives a clear missing-file error. The development sample is selected uniformly without replacement from unique `id_student` values, with all learner-course-presentation rows retained for each selected learner. Default is 6,000 learners; configure it between 5,000 and 7,000 and keep the seed stable for reproducibility. Since learners can appear in multiple presentations, the resulting modeling row count can exceed the learner count:

```powershell
python ml\src\explore_oulad.py --data-dir "D:\my files\anonymisedData" --sample-size 6000 --seed 42
```

Launch the notebook from the repo root with `jupyter lab ml\notebooks\01_oulad_exploration.ipynb`. Set the `DATA_DIR` variable in its first code cell if the files are in a different location. The notebook invokes the same script and therefore produces the same reports.

## Reports

The script creates aggregate-only files in `ml/reports/`:

- `csv_structure_summary.csv`: dimensions, actual columns/dtypes, and candidate keys.
- `missing_values_summary.csv`: per-column missing count and percentage.
- `data_quality_summary.csv`: exact duplicate rows and candidate-key duplicate/null counts.
- `join_relationships_summary.csv`: aggregate unmatched key counts for proposed table relationships.
- `feature_dictionary.csv`: source, calculation, keys, cutoff availability, status, missingness and risk.
- `target_and_merge_plan.md`: observed target counts, unit of analysis, sample summary, cutoff, join plan and limitations.

The sample's unique learner count, resulting composite-key row count, and class mix are reported, but sampled learner records are not exported. Phase 1 prepares this sample definition; it does not train a model.

## Initial modeling proposal (requires team agreement)

Use one learner-course-presentation row as the analysis unit. Proposed binary outcome: `Withdrawn` = 1; `Pass`, `Fail`, and `Distinction` = 0; missing or unexpected results are unknown/excluded. Do not use `final_result` as an input feature. Day 30 after presentation start is a provisional discussion cutoff only; filter event data to `date <= 30` before aggregating. OULAD dates are relative and do not establish calendar start dates.

Aggregate assessment and VLE events separately to the base composite key (`id_student`, `code_module`, `code_presentation`) before joining. Join assessment metadata on `id_assessment`, VLE metadata on resource/module/presentation keys, and validate one-to-many/many-to-one cardinality and row counts. Never join event-level assessment rows directly to event-level VLE rows. `date_unregistration` may expose withdrawal/future outcome, and its missingness does not imply completion. Missing assessment scores do not by themselves prove missed submissions. Review disability, age, and deprivation fields for privacy and fairness.

See `reports/target_and_merge_plan.md` after running the script for dataset-derived values.

## Phase 2: learner feature preparation

`src/prepare_oulad.py` validates all seven CSV schemas and key columns, builds the learner-course-presentation base, aggregates assessment and VLE activity separately, attaches cutoff-safe registration features, creates the proposed target, and checks cardinality after each merge. The default output sample is **6,000 unique eligible learners** (seed 42), retaining every eligible course-presentation row for each selected learner; this may produce more than 6,000 output rows. Set `--sample-learners` to another value in the requested 5,000–7,000 range or to a value at least as large as the eligible population to include everyone.

Run from the repository root:

```powershell
python -m ml.src.prepare_oulad --data-dir "D:\my files\anonymisedData" --output ml\data\processed\oulad_learner_features.csv --cutoff-day 30 --sample-learners 6000 --seed 42
```

By default, output goes to `ml/data/processed/oulad_learner_features.csv`; aggregate documentation goes to `ml/reports/phase2_preparation_report.md` and `ml/reports/phase2_feature_dictionary.csv`. Use `--report` and `--feature-dictionary` to change those paths. Processed learner data stays git-ignored. Do not place output files in the raw data directory.

Install the packages in `requirements.txt` using the environment steps above. Run the synthetic tests (no real OULAD files required) from the repository root:

```powershell
python -m pytest ml\tests -q
```

### Output schema and safeguards

The dataset contains one row per (`id_student`, `code_module`, `code_presentation`) and a `target_withdrawn` label. The proposal maps `Withdrawn` to 1 and `Pass`, `Fail`, and `Distinction` to 0; missing or unsupported outcomes are excluded. `final_result` is used only to construct the target and is not exported. `id_student` remains as an identifier for joins and evaluation, not a predictor.

The configurable cutoff is a relative course day and is **inclusive** (`date <= cutoff`, default day 30) for VLE events, assessment submissions/due dates, and registration timing. Negative relative dates are retained in total activity and registration values when observed by the cutoff; early VLE windows start at day 0. The pipeline does not infer calendar dates. It excludes `date_unregistration` entirely. Assessment due/submission counts are built from validated `id_assessment` metadata. Banked assessment records (`is_banked=1`, observed at relative day -1 in the supplied file) are counted separately and excluded from current submission and unsubmitted-assessment counts. An assessment without a current submission record by the cutoff is not asserted to be a confirmed missed assessment. Assessment score features are omitted because the files have no mark-release timestamp to establish score availability at day 30.

VLE events are checked against `vle.csv` on (`id_site`, `code_module`, `code_presentation`) and aggregated before feature merging. Exact duplicate VLE rows within the selected learners are removed because they repeat all source values; same-key rows with differing click counts are retained and summed. Counts of removed exact rows are reported. Learners with no observed VLE events receive zero activity counts, an explicit no-activity indicator, and a missing days-since-last-activity value. Each aggregate is merged one-to-one to the base and row counts are checked.

Sensitive context fields (`gender`, `region`, `age_band`, `imd_band`, and `disability`) are retained for audit/analysis but need a privacy and fairness review before use in training. Missing context is preserved; imputation and encoding belong inside training folds to avoid evaluation leakage. Repeated learners must be grouped appropriately in future train/test splits. The cutoff and binary target remain provisional Phase 1 proposals pending team agreement.

## Phases 3–8: verified baseline, evaluation, and inference

The prepared local cohort and saved artifact have been checked against the canonical schema. The current local sample contains 6,776 learner-course-presentation rows from 6,000 learners, with no duplicate composite keys. `target_withdrawn=1` denotes OULAD `Withdrawn`; Pass, Fail, and Distinction map to 0. The target and identifiers are not model inputs.

Train the reproducible Random Forest baseline from the repository root. Use a new artifact path when you need to preserve the existing local model:

```powershell
python -m ml.src.training.train --data ml/data/processed/oulad_learner_features.csv --artifact ml/artifacts/churn_model.joblib --seed 42
```

Training uses a deterministic 60/20/20 `GroupShuffleSplit` by `id_student`; the preprocessing pipeline is fitted on training learners only. It writes the model and sidecar metadata and evaluation JSON. The existing artifact was loaded in a separate Python process and scored against all 6,776 local prepared rows; this is an offline verification, not evidence of application/database integration.

The stable feature schema is [oulad-learner-v1.json](schemas/oulad-learner-v1.json). To batch-score a feature-only CSV (identifiers plus the exact 22 feature columns, with no target column):

```powershell
python -m ml.src.inference.batch_predict --input input_features.csv --output predictions.csv --artifact ml/artifacts/churn_model.joblib
```

The command refuses an existing output file, duplicate or missing learner-course keys, target columns, and schema mismatches. Its output includes the composite identifier, probability, risk band, model version, and UTC timestamp. Prediction CSVs contain learner identifiers; keep them in approved local storage and do not commit them.

`ml.src.explainability.shap_explainer.explain_with_shap` can return best-effort SHAP contributions grouped to the canonical feature columns. These describe model contribution, not cause. `ml.src.recommendations.recommendation_rules.recommend_for_records` emits only suggestions tied to observed day-30 activity/assessment indicators; each requires human review and includes its evidence and limitation. Neither capability persists data or triggers an intervention.

### Day-30 candidate experiment

The legacy `churn_model.joblib` was trained on the unfiltered outcome cohort and must not be treated as a valid day-30 early-warning model. To build a separately versioned candidate without overwriting it:

```powershell
python -m ml.src.training.day30_experiment --seed 42
```

This uses `studentRegistration.date_registration` and `date_unregistration` to select records registered by day 30 and still registered after day 30 (or with no recorded unregistration). Withdrawn labels without a timed unregistration are excluded. It trains on 2013B/2013J, validates on 2014B, and holds 2014J for a single final temporal test, excluding repeat learners across all three partitions. A second forward fold is reported as a variability check. Outputs are a new `churn_model_day30_candidate` artifact and aggregate-only report at `ml/reports/day30_experiment_evaluation.json`; the command refuses to overwrite any output.

The current candidate's temporal-test recall is low. Its 0.50 decision threshold is retained only as a provisional baseline because no operational cost matrix has been approved. Validation-only threshold sensitivity is included in the report; the final test was not used to pick a threshold. See [the day-30 audit](reports/day30_prediction_audit.md) before interpreting the scores.

### Verified baseline limits and decisions

- The saved artifact version is `churnshield-oulad-rf-1.0.0`; the input contract is `oulad-learner-v1`.
- The evaluation is a single random learner-grouped holdout on a 6,000-learner development sample. It is not temporal, external, or population-representative validation.
- `target_withdrawn` and the day-30 cutoff remain proposals requiring domain-owner approval. Do not use the model for operational intervention until these definitions, fairness, calibration, threshold selection, and prospective validation are reviewed.
- Risk bands (low below 0.30, medium from 0.30 to below 0.70, high from 0.70) and the 0.50 evaluation decision threshold are provisional and distinct.
- No live API, backend persistence, production model serving, or online drift monitoring is implemented or verified by this ML package.

See [the model card](../docs/model-card.md) for exact held-out metrics, configuration, and limitations. Run tests from the repository root with `python -m pytest ml/tests -q`.
