# ChurnShield ML: OULAD Phase 1

This phase documents the Open University Learning Analytics Dataset (OULAD), checks its seven CSV tables, proposes a withdrawal target and day-30 prediction cutoff, and records a safe feature/merge plan. It does not change frontend or backend code or train a model.

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
