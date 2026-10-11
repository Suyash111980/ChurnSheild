# OULAD target, sampling, and merge plan

## Observed analysis unit and target

`studentInfo.csv` contains **32,593** learner-course-presentation rows, **28,785** unique learners, and **0** duplicate composite keys (`id_student`, `code_module`, `code_presentation`). A learner may therefore contribute multiple course-presentation records. Unknown/missing outcomes: **0**.

Proposed binary target (requires team confirmation): `Withdrawn` = 1; `Pass`, `Fail`, `Distinction` = 0; missing or unexpected results excluded. Recognized outcome counts: positive **10,156**; negative **22,437**.

| final_result | count | percent of all base rows |
|---|---:|---:|
| Pass | 12361 | 37.93% |
| Withdrawn | 10156 | 31.16% |
| Fail | 7052 | 21.64% |
| Distinction | 3024 | 9.28% |

## Development sample

Uniform random sample without replacement of unique learners, configured by `--sample-size` (default 6,000) and `--seed` (default 42); all composite-key course-presentation rows belonging to sampled learners are retained. Thus the number of sampled learner-course-presentation rows can exceed the requested learner count. Event tables must then be filtered to these sampled composite keys, while aggregation happens after applying the day-30 cutoff. This script reports both sample learner count and row count/class distribution but does not export sampled learner rows.

Sampled unique learners: **6,000**; sampled learner-course-presentation rows: **6,776**.

| sample outcome (learner-course-presentation rows) | count | percent of sample rows |
|---|---:|---:|
| Pass | 2577 | 38.03% |
| Withdrawn | 2149 | 31.71% |
| Fail | 1414 | 20.87% |
| Distinction | 636 | 9.39% |

## Provisional cutoff and leakage

Use **day 30 after presentation start** as an initial design assumption for team discussion, not an approved modeling definition. OULAD event dates are relative days; do not infer calendar start dates. Apply `date <= 30` before any VLE activity aggregation. Assessment dates and submission dates must be verified as comparable relative timelines. `final_result` is target-only. `date_unregistration` is unsafe unless its event timing and use case are independently validated; it can directly reveal withdrawal. Missing score does not prove a missed submission, and a missing unregistration date does not prove completion. Review disability, age, and deprivation proxies for privacy/fairness before modeling.

## Table observations

- Assessment metadata: 206 rows; `assessment_type` values: TMA (106), CMA (76), Exam (24); `date` nonmissing=195.
- Student assessment events: 173,912 rows; missing scores=173; submission date field values/range are inspectable in schema and quality reports.
- Student VLE events: 10,655,280 rows; total clicks=39605099; relative date range=-25 to 269.
- Registration records: 32,593; missing unregistration dates=22521.
- Courses: 22; VLE metadata rows: 6,364.

## Proposed merge order

1. Start with `studentInfo.csv`; confirm uniqueness of the composite key `id_student, code_module, code_presentation`.
2. Join course metadata from `courses.csv` on `code_module`, `code_presentation` (many-to-one expected).
3. Join registration on the full composite learner-course-presentation key; validate cardinality.
4. Join assessment metadata to student submissions on `id_assessment`, then validate that module/presentation metadata agrees. Aggregate assessment events by the base composite key before joining to base.
5. Join VLE events to resource metadata on `id_site`, `code_module`, `code_presentation`; aggregate VLE events by the base composite key after cutoff filtering, then join.
6. Validate row counts/cardinality after each merge and verify the final composite key remains unique. Never join assessment event rows directly to VLE event rows.

Observed aggregate join coverage:
- `studentInfo.csv` → `courses.csv` on `code_module;code_presentation`: 0 unmatched out of 22 distinct left keys (unique course-presentation keys).
- `studentInfo.csv` → `studentRegistration.csv` on `id_student;code_module;code_presentation`: 0 unmatched out of 32,593 distinct left keys (unique learner-course-presentation keys).
- `studentInfo.csv` → `studentVle.csv` on `id_student;code_module;code_presentation`: 3,365 unmatched out of 32,593 distinct left keys (base learner-course-presentation keys with any VLE records).
- `studentVle.csv` → `vle.csv` on `id_site;code_module;code_presentation`: 0 unmatched out of 6,268 distinct left keys (unique VLE resource-module-presentation keys).
- `assessments.csv` → `courses.csv` on `code_module;code_presentation`: 0 unmatched out of 22 distinct left keys (assessment course-presentation keys).
- `studentAssessment.csv` → `assessments.csv` on `id_assessment`: 0 unmatched out of 188 distinct left keys (unique assessment identifiers).
- `studentAssessment.csv + assessments.csv` → `studentInfo.csv` on `id_student;code_module;code_presentation`: 0 unmatched out of 25,843 distinct left keys (unique learner-assessment combinations mapped to course-presentation).

Expected key candidates and observed uniqueness checks are in `csv_structure_summary.csv`, `data_quality_summary.csv`, and `join_relationships_summary.csv`. The VLE candidate key `(id_student, code_module, code_presentation, id_site, date)` has 2,195,960 repeated rows; 787,170 rows are exact duplicates. Investigate these event repeats before building features; they do not break the one-row-per-base-key design if the event table is aggregated safely. All reports are aggregate and omit learner identifiers and individual records.

## Limitations / checks for the team

- Confirm the binary target definition, cutoff, exact meaning of relative assessment dates, and whether repeated learners require grouped/time-aware validation splits.
- Review missingness, duplicates, unmatched join counts and sensitive feature policy before feature engineering.
- Do not interpret target distribution in a uniform development sample as the population rate without accounting for sampling.
