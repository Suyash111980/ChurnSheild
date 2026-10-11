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
