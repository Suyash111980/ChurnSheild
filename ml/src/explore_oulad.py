"""Explore the seven OULAD tables and write privacy-safe aggregate reports.

Raw CSVs are read in place; no learner-level rows are exported.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


FILES = [
    "studentInfo.csv", "studentAssessment.csv", "assessments.csv",
    "studentVle.csv", "studentRegistration.csv", "courses.csv", "vle.csv",
]
KEYS = {
    "studentInfo.csv": ["id_student", "code_module", "code_presentation"],
    "studentAssessment.csv": ["id_student", "id_assessment"],
    "assessments.csv": ["id_assessment"],
    "studentVle.csv": ["id_student", "code_module", "code_presentation", "id_site", "date"],
    "studentRegistration.csv": ["id_student", "code_module", "code_presentation"],
    "courses.csv": ["code_module", "code_presentation"],
    "vle.csv": ["id_site", "code_module", "code_presentation"],
}
BASE_KEYS = ["id_student", "code_module", "code_presentation"]


def read_inputs(data_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [name for name in FILES if not (data_dir / name).is_file()]
    if missing:
        expected = "\n".join(f"  - {name}" for name in missing)
        raise FileNotFoundError(
            f"Missing required OULAD file(s) in {data_dir}:\n{expected}\n"
            "Place all seven source CSVs in that directory or pass --data-dir."
        )
    tables = {}
    for name in FILES:
        print(f"Loading {name} ...", flush=True)
        tables[name] = pd.read_csv(data_dir / name, low_memory=False)
    return tables


def candidate_key_result(frame: pd.DataFrame, key: list[str]) -> tuple[str, int, int]:
    present = [col for col in key if col in frame.columns]
    if len(present) != len(key):
        return "unavailable: missing " + ", ".join(set(key) - set(present)), 0, 0
    null_rows = int(frame[present].isna().any(axis=1).sum())
    duplicate_rows = int(frame.duplicated(present, keep="first").sum())
    return ";".join(present), duplicate_rows, null_rows


def write_reports(tables: dict[str, pd.DataFrame], reports: Path, sample_size: int, seed: int) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    structures, missing_rows, quality_rows = [], [], []
    for name, frame in tables.items():
        key_text, key_dupes, key_nulls = candidate_key_result(frame, KEYS[name])
        structures.append({
            "file": name, "exists": True, "load_status": "loaded",
            "rows": len(frame), "columns": len(frame.columns),
            "column_names": " | ".join(map(str, frame.columns)),
            "dtypes": " | ".join(f"{col}:{dtype}" for col, dtype in frame.dtypes.items()),
            "candidate_key": key_text,
        })
        for col in frame.columns:
            count = int(frame[col].isna().sum())
            missing_rows.append({"file": name, "column": col, "missing_count": count,
                                 "missing_pct": round(100 * count / max(len(frame), 1), 4)})
        quality_rows.append({
            "file": name, "exact_duplicate_rows": int(frame.duplicated().sum()),
            "candidate_key_duplicate_rows": key_dupes,
            "candidate_key_null_rows": key_nulls,
            "observed_quality_notes": "",
        })
    pd.DataFrame(structures).to_csv(reports / "csv_structure_summary.csv", index=False)
    pd.DataFrame(missing_rows).to_csv(reports / "missing_values_summary.csv", index=False)
    pd.DataFrame(quality_rows).to_csv(reports / "data_quality_summary.csv", index=False)

    info = tables["studentInfo.csv"]
    if not set(BASE_KEYS + ["final_result"]).issubset(info.columns):
        raise ValueError("studentInfo.csv must contain id_student, code_module, code_presentation, and final_result")
    duplicate_composites = int(info.duplicated(BASE_KEYS).sum())
    result_counts = info["final_result"].value_counts(dropna=False)
    total = len(info)
    result_lines = [
        f"| {('(missing)' if pd.isna(label) else str(label))} | {int(count)} | {100*count/total:.2f}% |"
        for label, count in result_counts.items()
    ]
    recognized = {"Withdrawn", "Pass", "Fail", "Distinction"}
    unknown_count = int((~info["final_result"].isin(recognized)).sum())
    valid_base = info.drop_duplicates(BASE_KEYS)
    sampled_learner_n = min(max(sample_size, 0), int(valid_base["id_student"].nunique()))
    sampled_ids = (valid_base["id_student"].drop_duplicates().sample(n=sampled_learner_n, random_state=seed)
                   if sampled_learner_n else pd.Series(dtype=valid_base["id_student"].dtype))
    sampled = valid_base[valid_base["id_student"].isin(sampled_ids)]
    sample_n = len(sampled)
    sampled_mix = sampled["final_result"].value_counts(dropna=False)
    sample_lines = [
        f"| {('(missing)' if pd.isna(label) else str(label))} | {int(count)} | {100*count/max(sample_n,1):.2f}% |"
        for label, count in sampled_mix.items()
    ]

    assessments = tables["assessments.csv"]
    submissions = tables["studentAssessment.csv"]
    vle = tables["studentVle.csv"]
    reg = tables["studentRegistration.csv"]
    courses = tables["courses.csv"]
    resources = tables["vle.csv"]
    quality_by_file = {row["file"]: row for row in quality_rows}
    quality_by_file["studentInfo.csv"]["observed_quality_notes"] = (
        f"final_result unexpected/missing={unknown_count:,}; additional rows beyond unique learner count="
        f"{len(info) - info['id_student'].nunique():,} (unique learners={info['id_student'].nunique():,})"
    )
    quality_by_file["studentAssessment.csv"]["observed_quality_notes"] = (
        f"score missing={int(submissions['score'].isna().sum()) if 'score' in submissions else 'n/a'}; "
        f"score outside 0-100={int((~submissions['score'].between(0, 100) & submissions['score'].notna()).sum()) if 'score' in submissions else 'n/a'}"
    )
    quality_by_file["assessments.csv"]["observed_quality_notes"] = (
        f"date missing={int(assessments['date'].isna().sum()) if 'date' in assessments else 'n/a'}; "
        f"weight total={assessments['weight'].sum() if 'weight' in assessments else 'n/a'} (inspect by course/presentation)"
    )
    quality_by_file["studentVle.csv"]["observed_quality_notes"] = (
        f"relative date range={vle['date'].min()}..{vle['date'].max()}; "
        f"negative clicks={int((vle['sum_click'] < 0).sum())}; duplicate rows and repeated candidate keys require investigation"
    )
    quality_by_file["studentRegistration.csv"]["observed_quality_notes"] = (
        f"registration date missing={int(reg['date_registration'].isna().sum())}; "
        f"unregistration date missing={int(reg['date_unregistration'].isna().sum())} (not evidence of completion)"
    )
    quality_by_file["vle.csv"]["observed_quality_notes"] = (
        f"week_from missing={int(resources['week_from'].isna().sum()) if 'week_from' in resources else 'n/a'}; "
        f"week_to missing={int(resources['week_to'].isna().sum()) if 'week_to' in resources else 'n/a'}"
    )
    quality_by_file["courses.csv"]["observed_quality_notes"] = "presentation length recorded in module_presentation_length"
    pd.DataFrame(quality_rows).to_csv(reports / "data_quality_summary.csv", index=False)
    def field_values(frame: pd.DataFrame, col: str) -> str:
        if col not in frame:
            return "not present"
        vals = frame[col].dropna().astype(str).value_counts().head(20)
        return ", ".join(f"{v} ({n})" for v, n in vals.items()) or "no non-missing values"

    features = [
        ["learner/course context", "studied_credits", "studentInfo", "Base-table value", ";".join(BASE_KEYS), "By cutoff", "Check missingness", "candidate", "Do not use if outcome proxy is introduced"],
        ["learner/course context", "age_band, highest_education, imd_band", "studentInfo", "Categorical context", ";".join(BASE_KEYS), "By cutoff", "See missing-values report", "candidate", "Fairness review; IMD/age are sensitive proxies"],
        ["learner/course context", "disability", "studentInfo", "Categorical indicator", ";".join(BASE_KEYS), "By cutoff", "See missing-values report", "requires_validation", "Sensitive attribute; privacy and fairness review before use"],
        ["learner/course context", "code_module, code_presentation", "studentInfo", "Base-table identifiers/context", ";".join(BASE_KEYS), "By cutoff", "Low expected; verify report", "candidate", "Presentation-specific temporal validation needed"],
        ["assessment behavior", "assessments due by day 30", "assessments", "Count metadata rows with date <= 30", "code_module, code_presentation; assessment_id", "Potentially", "Schedule coverage / null due dates", "requires_validation", "Confirm assessment date is relative to presentation start"],
        ["assessment behavior", "submissions, late/missed, score summaries by day 30", "studentAssessment + assessments", "Join assessment_id; filter submitted/due dates <= 30 then aggregate", ";".join(BASE_KEYS)+"; id_assessment", "Only after cutoff filter", "Missing score is not proof of non-submission", "requires_validation", "Scores/submissions after day 30 leak future behavior"],
        ["learning activity", "click total, active days, last activity, trends by day 30", "studentVle", "Filter date <= 30 then aggregate per learner-course-presentation", ";".join(BASE_KEYS), "Only after cutoff filter", "No activity may mean absent logging", "candidate", "Never include post-cutoff clicks; filter before aggregation"],
        ["registration", "date_registration", "studentRegistration", "Days relative to course start", ";".join(BASE_KEYS), "Likely", "Check missingness and date range", "requires_validation", "Relative-day semantics need confirmation"],
        ["registration", "date_unregistration", "studentRegistration", "Do not aggregate as predictor without event-time validation", ";".join(BASE_KEYS), "Unclear", "Missing is not completion", "exclude_due_to_leakage", "Can reveal withdrawal/future outcome"],
        ["outcome", "final_result / proposed withdrawal label", "studentInfo", "Withdrawn=1; Pass/Fail/Distinction=0; missing/unexpected excluded", ";".join(BASE_KEYS), "Outcome only", "Observed distribution in report", "exclude_due_to_leakage", "Target construction only; never a feature"],
    ]
    feature_cols = ["category", "feature", "source_table", "calculation", "join_keys", "available_by_day_30", "likely_missingness", "status", "leakage_fairness_risks"]
    pd.DataFrame(features, columns=feature_cols).to_csv(reports / "feature_dictionary.csv", index=False)

    def unmatched(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> int:
        left_keys = left[keys].drop_duplicates()
        right_keys = right[keys].drop_duplicates()
        return int(left_keys.merge(right_keys, on=keys, how="left", indicator=True)["_merge"].eq("left_only").sum())

    joins = [
        ("studentInfo.csv", "courses.csv", ["code_module", "code_presentation"], "unique course-presentation keys"),
        ("studentInfo.csv", "studentRegistration.csv", BASE_KEYS, "unique learner-course-presentation keys"),
        ("studentInfo.csv", "studentVle.csv", BASE_KEYS, "base learner-course-presentation keys with any VLE records"),
        ("studentVle.csv", "vle.csv", ["id_site", "code_module", "code_presentation"], "unique VLE resource-module-presentation keys"),
        ("assessments.csv", "courses.csv", ["code_module", "code_presentation"], "assessment course-presentation keys"),
    ]
    join_rows = []
    for left_name, right_name, keys, unit in joins:
        left_frame, right_frame = tables[left_name], tables[right_name]
        join_rows.append({"left_file": left_name, "right_file": right_name, "join_keys": ";".join(keys),
                          "unit_checked": unit, "distinct_left_keys": len(left_frame[keys].drop_duplicates()),
                          "distinct_right_keys": len(right_frame[keys].drop_duplicates()),
                          "unmatched_left_keys": unmatched(left_frame, right_frame, keys)})
    assessment_refs = submissions[["id_assessment"]].drop_duplicates()
    join_rows.append({"left_file": "studentAssessment.csv", "right_file": "assessments.csv",
                      "join_keys": "id_assessment", "unit_checked": "unique assessment identifiers",
                      "distinct_left_keys": len(assessment_refs),
                      "distinct_right_keys": len(assessments[["id_assessment"]].drop_duplicates()),
                      "unmatched_left_keys": unmatched(assessment_refs, assessments, ["id_assessment"])})
    assessment_link = submissions[["id_student", "id_assessment"]].drop_duplicates().merge(
        assessments[["id_assessment", "code_module", "code_presentation"]], on="id_assessment", how="left", validate="many_to_one"
    )
    assessment_link = assessment_link.dropna(subset=["code_module", "code_presentation"])
    join_rows.append({"left_file": "studentAssessment.csv + assessments.csv", "right_file": "studentInfo.csv",
                      "join_keys": ";".join(BASE_KEYS), "unit_checked": "unique learner-assessment combinations mapped to course-presentation",
                      "distinct_left_keys": len(assessment_link[BASE_KEYS].drop_duplicates()),
                      "distinct_right_keys": len(info[BASE_KEYS].drop_duplicates()),
                      "unmatched_left_keys": unmatched(assessment_link, info, BASE_KEYS)})
    pd.DataFrame(join_rows).to_csv(reports / "join_relationships_summary.csv", index=False)
    join_lines = [
        f"- `{row['left_file']}` → `{row['right_file']}` on `{row['join_keys']}`: "
        f"{row['unmatched_left_keys']:,} unmatched out of {row['distinct_left_keys']:,} distinct left keys "
        f"({row['unit_checked']})."
        for row in join_rows
    ]

    targetable = info[info["final_result"].isin(recognized)]
    withdrawal_n = int((targetable["final_result"] == "Withdrawn").sum())
    negative_n = int(targetable["final_result"].isin(["Pass", "Fail", "Distinction"]).sum())
    content = f"""# OULAD target, sampling, and merge plan

## Observed analysis unit and target

`studentInfo.csv` contains **{len(info):,}** learner-course-presentation rows, **{info['id_student'].nunique():,}** unique learners, and **{duplicate_composites:,}** duplicate composite keys (`id_student`, `code_module`, `code_presentation`). A learner may therefore contribute multiple course-presentation records. Unknown/missing outcomes: **{unknown_count:,}**.

Proposed binary target (requires team confirmation): `Withdrawn` = 1; `Pass`, `Fail`, `Distinction` = 0; missing or unexpected results excluded. Recognized outcome counts: positive **{withdrawal_n:,}**; negative **{negative_n:,}**.

| final_result | count | percent of all base rows |
|---|---:|---:|
{chr(10).join(result_lines)}

## Development sample

Uniform random sample without replacement of unique learners, configured by `--sample-size` (default {sample_size:,}) and `--seed` (default {seed}); all composite-key course-presentation rows belonging to sampled learners are retained. Thus the number of sampled learner-course-presentation rows can exceed the requested learner count. Event tables must then be filtered to these sampled composite keys, while aggregation happens after applying the day-30 cutoff. This script reports both sample learner count and row count/class distribution but does not export sampled learner rows.

Sampled unique learners: **{sampled_learner_n:,}**; sampled learner-course-presentation rows: **{sample_n:,}**.

| sample outcome (learner-course-presentation rows) | count | percent of sample rows |
|---|---:|---:|
{chr(10).join(sample_lines) if sample_lines else '| (empty) | 0 | 0.00% |'}

## Provisional cutoff and leakage

Use **day 30 after presentation start** as an initial design assumption for team discussion, not an approved modeling definition. OULAD event dates are relative days; do not infer calendar start dates. Apply `date <= 30` before any VLE activity aggregation. Assessment dates and submission dates must be verified as comparable relative timelines. `final_result` is target-only. `date_unregistration` is unsafe unless its event timing and use case are independently validated; it can directly reveal withdrawal. Missing score does not prove a missed submission, and a missing unregistration date does not prove completion. Review disability, age, and deprivation proxies for privacy/fairness before modeling.

## Table observations

- Assessment metadata: {len(assessments):,} rows; `assessment_type` values: {field_values(assessments, 'assessment_type')}; `date` nonmissing={int(assessments['date'].notna().sum()) if 'date' in assessments else 'n/a'}.
- Student assessment events: {len(submissions):,} rows; missing scores={int(submissions['score'].isna().sum()) if 'score' in submissions else 'n/a'}; submission date field values/range are inspectable in schema and quality reports.
- Student VLE events: {len(vle):,} rows; total clicks={int(vle['sum_click'].sum()) if 'sum_click' in vle else 'n/a'}; relative date range={vle['date'].min() if 'date' in vle else 'n/a'} to {vle['date'].max() if 'date' in vle else 'n/a'}.
- Registration records: {len(reg):,}; missing unregistration dates={int(reg['date_unregistration'].isna().sum()) if 'date_unregistration' in reg else 'n/a'}.
- Courses: {len(courses):,}; VLE metadata rows: {len(resources):,}.

## Proposed merge order

1. Start with `studentInfo.csv`; confirm uniqueness of the composite key `{', '.join(BASE_KEYS)}`.
2. Join course metadata from `courses.csv` on `code_module`, `code_presentation` (many-to-one expected).
3. Join registration on the full composite learner-course-presentation key; validate cardinality.
4. Join assessment metadata to student submissions on `id_assessment`, then validate that module/presentation metadata agrees. Aggregate assessment events by the base composite key before joining to base.
5. Join VLE events to resource metadata on `id_site`, `code_module`, `code_presentation`; aggregate VLE events by the base composite key after cutoff filtering, then join.
6. Validate row counts/cardinality after each merge and verify the final composite key remains unique. Never join assessment event rows directly to VLE event rows.

Observed aggregate join coverage:
{chr(10).join(join_lines)}

Expected key candidates and observed uniqueness checks are in `csv_structure_summary.csv`, `data_quality_summary.csv`, and `join_relationships_summary.csv`. The VLE candidate key `(id_student, code_module, code_presentation, id_site, date)` has {quality_by_file['studentVle.csv']['candidate_key_duplicate_rows']:,} repeated rows; {quality_by_file['studentVle.csv']['exact_duplicate_rows']:,} rows are exact duplicates. Investigate these event repeats before building features; they do not break the one-row-per-base-key design if the event table is aggregated safely. All reports are aggregate and omit learner identifiers and individual records.

## Limitations / checks for the team

- Confirm the binary target definition, cutoff, exact meaning of relative assessment dates, and whether repeated learners require grouped/time-aware validation splits.
- Review missingness, duplicates, unmatched join counts and sensitive feature policy before feature engineering.
- Do not interpret target distribution in a uniform development sample as the population rate without accounting for sampling.
"""
    (reports / "target_and_merge_plan.md").write_text(content, encoding="utf-8")
    print(f"Wrote aggregate reports to {reports}")
    print(f"Base rows={len(info):,}; unique learners={info['id_student'].nunique():,}; duplicate composite keys={duplicate_composites:,}")
    print(f"Sample learners={sampled_learner_n:,}; learner-course-presentation rows={sample_n:,} (requested learners={sample_size:,}; seed={seed})")
    print("final_result counts:")
    print(result_counts.to_string())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    project_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--data-dir", type=Path, default=project_root / "ml" / "data" / "raw",
                        help="Directory containing all seven OULAD source CSVs")
    parser.add_argument("--reports-dir", type=Path, default=project_root / "ml" / "reports")
    parser.add_argument("--sample-size", type=int, default=6000, help="Uniform sample size from base composite rows (default: 6000)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        tables = read_inputs(args.data_dir.expanduser().resolve())
        write_reports(tables, args.reports_dir.expanduser().resolve(), args.sample_size, args.seed)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
