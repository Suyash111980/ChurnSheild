# ChurnShield ML: OULAD Phase 1

This ML area contains Phase 1 OULAD exploration and the Phase 2 reproducible, cutoff-safe learner-feature preparation pipeline. The Phase 2 pipeline prepares data for later modeling; it does not fit a model. Frontend and backend code are outside this scope.

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
## Phase 3: Model training and inference

Phase 3 trains a Random Forest and a logistic regression reference model from the Phase 2 prepared learner table. It saves versioned fitted pipelines, metrics, feature schema, and Random Forest feature importance under `ml/artifacts/`. Generated model artifacts are ignored by Git under the existing data/artifact policy; produce them locally using the command below before integration.

### Target, observation window, and leakage controls

The unit is one learner-course-presentation row. The target is `target_withdrawn`: `Withdrawn` is positive class `1`; `Pass`, `Fail`, and `Distinction` are class `0`. Unknown outcomes are excluded by Phase 2. Features use information available through the inclusive day-30 cutoff. Phase 2 excludes `final_result` and `date_unregistration` from predictors, excludes assessment scores without a release timestamp, validates join cardinality, and aggregates VLE/assessment events before joining. Student IDs are used only to keep all rows for one learner in the same split and may be returned as metadata; they are never model inputs. `student_name` and `ml/data/sample/student_display.csv` are not used by training or inference.

### Install and run

Tested with Python 3.14.7, pandas 3.0.6, NumPy 2.5.4, scikit-learn 1.9.1, joblib 1.6.0, and pytest 8.4.2. Install the ML dependencies in your project environment:

```powershell
python -m pip install -r ml\requirements.txt
```

Prepare the configured six-thousand-student sample (seed 42) from the seven source CSVs:

```powershell
python -m ml.src.prepare_oulad --data-dir "D:\my files\anonymisedData" --output ml\data\processed\oulad_learner_features.csv --cutoff-day 30 --sample-learners 6000 --seed 42
```

Train both classifiers and save a new timestamped artifact version; training does not overwrite earlier versions:

```powershell
python -m ml.src.training.train --data ml\data\processed\oulad_learner_features.csv --artifact-dir ml\artifacts --seed 42 --threshold 0.5 --n-estimators 300 --n-jobs -1
```

The baseline is `LogisticRegression(max_iter=1000, class_weight='balanced')`. The required model is `RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight='balanced_subsample', random_state=42)`. Both models use separate copies of the same preprocessing design, fitted on training rows only. Numeric values are median-imputed and standardized; categories use a missing token and one-hot encoding with unknown categories ignored. Threshold 0.5 is fixed in advance and is not selected against the test set. Class weights compensate for the approximately 68/32 label distribution in the training data; the test distribution is left unchanged.

### Verified OULAD run

A fresh preparation from `D:\my files\anonymisedData` completed with 6,776 rows and 6,000 unique learners. Labels were 4,627 class-0 rows and 2,149 class-1 rows. The stratified group split used `id_student`: training 4,064 rows / 3,610 students; validation 1,356 / 1,202; test 1,356 / 1,188. No learner crossed splits. Test class counts were 926 class 0 and 430 class 1. Validation was not used to tune the model or threshold.

Held-out test results at threshold 0.5 (precision/recall/F1 use binary averaging for positive label 1):

| Model | Precision | Recall | F1 | ROC-AUC | Confusion matrix (actual rows 0,1; predicted columns 0,1) |
|---|---:|---:|---:|---:|---|
| Logistic regression baseline | 0.6674 | 0.6767 | 0.6721 | 0.8238 | `[[781, 145], [139, 291]]` |
| Random Forest | 0.7670 | 0.5512 | 0.6414 | 0.8158 | `[[854, 72], [193, 237]]` |

The Random Forest has higher precision but lower recall, F1, and ROC-AUC than this baseline on the held-out sample. At this threshold it misses 193 withdrawn rows versus 139 for the baseline; the baseline raises more false positives (145 versus 72). The classifier is implemented as required, but this run does not establish it as the better model. Evaluate threshold and model choices on a future validation workflow before operational use. OULAD is a historical educational dataset, so these results do not establish performance for a live cohort.

The verified local model version from this run is `phase3-20261013T131618574585Z`. Its files are under `ml/artifacts/phase3-20261013T131618574585Z/`: `random_forest_pipeline.joblib`, `baseline_logistic_pipeline.joblib`, `metadata.json`, `evaluation.json`, `feature_schema.json`, and `feature_importance.json`. Metadata/metrics contain no learner-level rows. Feature importance is impurity-based and is not causal evidence. The artifact folder is ignored by Git and must be regenerated or transferred through the team's approved model-artifact process on another machine.

### Inference contract

The inference module accepts **prepared feature rows**, not the seven raw OULAD CSVs. Its required predictors are the 28 fields below. Every predictor column must exist; values may be missing and are imputed by the saved pipeline. Numeric fields must be numeric or missing. Unseen categories are accepted and produce all-zero one-hot columns for that field. Extra columns, including target/IDs/display names, are ignored for modeling. `id_student`, `code_module`, and `code_presentation` are copied to outputs when present; `code_module` and `code_presentation` are also predictors. The target and names are never predictors.

Categorical input columns:

- `code_module` — categorical/string
- `code_presentation` — categorical/string
- `gender` — categorical/string
- `region` — categorical/string
- `highest_education` — categorical/string
- `imd_band` — categorical/string
- `age_band` — categorical/string
- `disability` — categorical/string

Numeric input columns:

- `num_of_prev_attempts` — numeric
- `studied_credits` — numeric
- `module_presentation_length` — numeric
- `registration_record_present` — numeric
- `registration_by_cutoff` — numeric
- `registration_day_at_cutoff` — numeric
- `registration_date_missing` — numeric
- `assessments_due_by_cutoff` — numeric
- `assessment_submissions_by_cutoff` — numeric
- `assessment_late_submissions_by_cutoff` — numeric
- `assessments_without_submission_recorded_by_cutoff` — numeric
- `assessment_banked_results_by_cutoff` — numeric
- `assessment_submission_rate_by_cutoff` — numeric
- `vle_total_clicks_by_cutoff` — numeric
- `vle_active_days_by_cutoff` — numeric
- `vle_distinct_resources_by_cutoff` — numeric
- `vle_clicks_day_0_7` — numeric
- `vle_clicks_day_8_cutoff` — numeric
- `vle_has_activity_by_cutoff` — numeric
- `vle_days_since_last_activity_at_cutoff` — numeric

Make one prediction per row from a CSV and a specific local artifact version:

```powershell
python -m ml.src.inference.predict --data path\to\prepared_rows.csv --artifact-dir ml\artifacts\phase3-20261013T131618574585Z --output predictions.csv
```

The output columns are optional input identifiers (`id_student`, `code_module`, `code_presentation`), `predicted_class` (0/1 using stored threshold), `withdrawal_risk_probability` (float 0–1 for positive class 1), and `model_version`. Inference only loads the trusted local pipeline; it does not retrain. Missing artifact files raise `FileNotFoundError`; missing predictors or nonnumeric values raise `ValueError`. For example, the module entry point used in the verified four-row fresh-process smoke run was `ml.src.inference.predict`.

### Exact fitted Random Forest input columns

Preprocessing expanded the raw inputs into 67 ordered model columns. This list was generated from the fitted `ColumnTransformer.get_feature_names_out()` output and verified against the fitted Random Forest's `n_features_in_`. The machine-readable copy in `feature_schema.json` belongs to the artifact version above.

- `numeric__num_of_prev_attempts`
- `numeric__studied_credits`
- `numeric__module_presentation_length`
- `numeric__registration_record_present`
- `numeric__registration_by_cutoff`
- `numeric__registration_day_at_cutoff`
- `numeric__registration_date_missing`
- `numeric__assessments_due_by_cutoff`
- `numeric__assessment_submissions_by_cutoff`
- `numeric__assessment_late_submissions_by_cutoff`
- `numeric__assessments_without_submission_recorded_by_cutoff`
- `numeric__assessment_banked_results_by_cutoff`
- `numeric__assessment_submission_rate_by_cutoff`
- `numeric__vle_total_clicks_by_cutoff`
- `numeric__vle_active_days_by_cutoff`
- `numeric__vle_distinct_resources_by_cutoff`
- `numeric__vle_clicks_day_0_7`
- `numeric__vle_clicks_day_8_cutoff`
- `numeric__vle_has_activity_by_cutoff`
- `numeric__vle_days_since_last_activity_at_cutoff`
- `categorical__code_module_AAA`
- `categorical__code_module_BBB`
- `categorical__code_module_CCC`
- `categorical__code_module_DDD`
- `categorical__code_module_EEE`
- `categorical__code_module_FFF`
- `categorical__code_module_GGG`
- `categorical__code_presentation_2013B`
- `categorical__code_presentation_2013J`
- `categorical__code_presentation_2014B`
- `categorical__code_presentation_2014J`
- `categorical__gender_F`
- `categorical__gender_M`
- `categorical__region_East Anglian Region`
- `categorical__region_East Midlands Region`
- `categorical__region_Ireland`
- `categorical__region_London Region`
- `categorical__region_North Region`
- `categorical__region_North Western Region`
- `categorical__region_Scotland`
- `categorical__region_South East Region`
- `categorical__region_South Region`
- `categorical__region_South West Region`
- `categorical__region_Wales`
- `categorical__region_West Midlands Region`
- `categorical__region_Yorkshire Region`
- `categorical__highest_education_A Level or Equivalent`
- `categorical__highest_education_HE Qualification`
- `categorical__highest_education_Lower Than A Level`
- `categorical__highest_education_No Formal quals`
- `categorical__highest_education_Post Graduate Qualification`
- `categorical__imd_band_0-10%`
- `categorical__imd_band_10-20`
- `categorical__imd_band_20-30%`
- `categorical__imd_band_30-40%`
- `categorical__imd_band_40-50%`
- `categorical__imd_band_50-60%`
- `categorical__imd_band_60-70%`
- `categorical__imd_band_70-80%`
- `categorical__imd_band_80-90%`
- `categorical__imd_band_90-100%`
- `categorical__imd_band___MISSING__`
- `categorical__age_band_0-35`
- `categorical__age_band_35-55`
- `categorical__age_band_55<=`
- `categorical__disability_N`
- `categorical__disability_Y`

Run all ML tests from the repository root:

```powershell
python -m pytest ml\tests -v
```

Verified result after Phase 3 implementation: **51 passed**. The project-level backend test suite was not run; it is outside this ML task.
