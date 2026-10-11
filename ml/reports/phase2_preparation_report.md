# Phase 2 OULAD preparation report

- Cutoff: day 30.0 inclusive.
- Target: Withdrawn=1; Pass/Fail/Distinction=0; missing/unsupported outcomes excluded.
- Requested sample: 6000 unique learners; seed 42.
- Final dataset: 6,776 rows × 30 columns.
- Unique learners in output: 6,000.
- Composite-key duplicate rows: 0.
- Processed data: `ml/data/processed/oulad_learner_features.csv`.
- Feature dictionary: `ml/reports/phase2_feature_dictionary.csv`.

## Input row counts

| Table | Rows |
|---|---:|
| `studentInfo.csv` | 32,593 |
| `studentAssessment.csv` | 173,912 |
| `assessments.csv` | 206 |
| `studentVle.csv` | 10,655,280 |
| `studentRegistration.csv` | 32,593 |
| `courses.csv` | 22 |
| `vle.csv` | 6,364 |

## Row counts and target

- Base rows: 32,593 (28,785 unique learners).
- Target-eligible rows before sampling: 32,593.
- Unknown/missing target rows excluded: 0.
- Sampled output base rows: 6,776 across 6,000 unique learners.

| target_withdrawn | count | proportion |
|---:|---:|---:|
| 0 | 4,627 | 68.2851% |
| 1 | 2,149 | 31.7149% |

## Merge validation

| Aggregate | Rows before | Rows after | Unmatched base rows |
|---|---:|---:|---:|
| course_metadata | 32,593 | 32,593 | 0 |
| registration | 32,593 | 32,593 | 0 |
| assessment | 6,776 | 6,776 | 0 |
| VLE | 6,776 | 6,776 | 0 |

## Missing values in output

| Column | Missing | Percent |
|---|---:|---:|
| `imd_band` | 246 | 3.6305% |
| `registration_day_at_cutoff` | 19 | 0.2804% |
| `assessment_submission_rate_by_cutoff` | 1,182 | 17.4439% |
| `vle_days_since_last_activity_at_cutoff` | 792 | 11.6883% |

## Join and data checks

- Missing assessment scores in source: 173; scores are not predictors because their release time is unavailable.
- base_records_without_registration_row: 0.
- registration_rows_without_base_record: 0.
- assessment_rows_without_metadata: 0.
- assessment_rows_without_base_record: 0.
- distinct_assessment_base_keys_without_base_record: 0.
- assessment_metadata_rows_due_by_cutoff: 17.
- assessment_submission_rows_by_cutoff_in_sample: 5,524.
- banked_assessment_rows_by_cutoff_in_sample: 362.
- sample_vle_rows_before_exact_deduplication: 2,264,238.
- sample_vle_exact_duplicate_rows_removed: 165,362.
- sample_vle_events_by_cutoff_after_deduplication: 596,754.
- sample_vle_resource_keys_unmatched: 0.
- sample_vle_learner_course_keys_without_base_record: 0.

## Assumptions and warnings

- Day 30 is a provisional Phase 1 cutoff, not team-approved; the boundary day is included.
- Assessment scores are omitted because score-release availability by cutoff cannot be verified.
- assessments_without_submission_recorded_by_cutoff is not proof of a confirmed missed assessment.
- Age, gender, region, disability and IMD attributes require privacy/fairness review.
- Exact duplicate VLE rows within selected learners are removed; same-key rows with differing clicks are retained and summed.

Assessment due dates use `assessments.date`; submissions use `studentAssessment.date_submitted`; VLE and registration dates are relative-day values. Every event feature uses `date <= cutoff` (inclusive). Negative relative days are retained for total activity/registration features because they were observed before the cutoff; the separate early-activity windows begin at day 0. No absolute calendar dates are inferred.
