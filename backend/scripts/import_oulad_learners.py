
"""Safely import OULAD studentInfo.csv into Supabase.

Default behavior is a dry run. Database writes require --apply,
--dataset-id for an existing owned dataset, and either --limit N or --all.
"""

import argparse
import sys
from pathlib import Path
from uuid import UUID

import pandas as pd

# Make the backend package importable when this script is run directly.
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.integrations.supabase_client import supabase  # noqa: E402

CSV_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "studentInfo.csv"

REQUIRED_COLUMNS = {
    "id_student",
    "code_module",
    "code_presentation",
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
    "num_of_prev_attempts",
    "studied_credits",
    "disability",
}

TEXT_COLUMNS = [
    "id_student",
    "code_module",
    "code_presentation",
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
]

UPSERT_COLUMNS = [
    "external_learner_id",
    "code_module",
    "code_presentation",
    "gender",
    "region",
    "highest_education",
    "imd_band",
    "age_band",
    "num_of_prev_attempts",
    "studied_credits",
    "disability",
]


def normalize_text(value):
    """Convert blank and '?' CSV values to database NULL."""
    if pd.isna(value):
        return None

    value = str(value).strip()
    if not value or value == "?":
        return None

    return value


def normalize_integer(value, column, default=None):
    if pd.isna(value) or str(value).strip() in ("", "?"):
        return default

    try:
        number = float(value)
        if not number.is_integer():
            raise ValueError
        return int(number)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid integer value in column '{column}'") from None


def normalize_disability(value):
    value = normalize_text(value)

    if value is None:
        return None
    if value.upper() == "Y":
        return True
    if value.upper() == "N":
        return False

    raise ValueError("Unexpected value in the disability column")


def prepare_records(frame, dataset_id=None):
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(sorted(missing))
        )

    records = []

    for _, row in frame.iterrows():
        student_id = normalize_text(row["id_student"])
        module = normalize_text(row["code_module"])
        presentation = normalize_text(row["code_presentation"])

        if not student_id or not module or not presentation:
            raise ValueError(
                "A row is missing its learner, module, or presentation identifier"
            )

        record = {
            "external_learner_id": student_id,
            "code_module": module,
            "code_presentation": presentation,
        }

        for column in TEXT_COLUMNS:
            if column == "id_student":
                continue
            record[column] = normalize_text(row[column])

        record["num_of_prev_attempts"] = normalize_integer(
            row["num_of_prev_attempts"],
            "num_of_prev_attempts",
            default=0,
        )
        record["studied_credits"] = normalize_integer(
            row["studied_credits"],
            "studied_credits",
        )
        record["disability"] = normalize_disability(row["disability"])

        if record["num_of_prev_attempts"] < 0:
            raise ValueError("Negative previous-attempt count encountered")

        credits = record["studied_credits"]
        if credits is not None and credits < 0:
            raise ValueError("Negative studied-credits value encountered")

        payload = {key: record[key] for key in UPSERT_COLUMNS if key in record}
        if dataset_id is not None:
            payload["dataset_id"] = str(dataset_id)
        records.append(payload)

    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write records to Supabase. Without this, runs a dry run.",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--limit",
        type=int,
        help="Process at most this many CSV rows (recommended for the first test).",
    )
    mode.add_argument(
        "--all",
        action="store_true",
        help="Process all CSV rows. Requires --apply for database writes.",
    )
    parser.add_argument(
        "--dataset-id",
        help="Existing owner-scoped dataset UUID for the imported learner rows.",
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    if args.apply and args.limit is None and not args.all:
        parser.error("For safety, use --apply --limit N or --apply --all")
    if args.apply and not args.dataset_id:
        parser.error("--apply requires --dataset-id for an existing owned dataset")
    if args.dataset_id:
        try:
            args.dataset_id = str(UUID(args.dataset_id))
        except ValueError:
            parser.error("--dataset-id must be a valid UUID")

    if not CSV_PATH.is_file():
        print(f"ERROR: CSV file not found: {CSV_PATH}")
        return 1

    try:
        # Read the CSV; do not display learner rows.
        frame = pd.read_csv(
            CSV_PATH,
            dtype={"id_student": "string"},
            keep_default_na=True,
        )

        if args.limit is not None:
            frame = frame.head(args.limit)

        records = prepare_records(frame, dataset_id=args.dataset_id)

        # Check duplicate keys within the selected input before writing.
        keys = [
            (
                item["external_learner_id"],
                item["code_module"],
                item["code_presentation"],
            )
            for item in records
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "Duplicate learner/module/presentation keys found in the selected CSV rows"
            )

        print("CSV validation passed.")
        print(f"Rows selected: {len(records)}")
        print(f"Source file: {CSV_PATH.name}")

        if not args.apply:
            print("Mode: DRY RUN — no database writes were made.")
            print("Next: review this result, then test with --apply --limit 10.")
            return 0

        if supabase is None:
            print("ERROR: Supabase client is not configured.")
            return 1

        # Upsert in small chunks. Re-running safely updates matching keys.
        batch_size = 100
        written = 0

        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            supabase.table("learners").upsert(
                batch,
                on_conflict="dataset_id,external_learner_id,code_module,code_presentation",
            ).execute()
            written += len(batch)
            print(f"Upsert requests completed for {written} of {len(records)} rows.")

        print("Import completed.")
        print(f"Rows submitted for upsert: {written}")
        print("No learner records were printed.")
        return 0

    except Exception as exc:
        # Avoid printing record data or credentials in error output.
        print(f"ERROR: Import stopped ({type(exc).__name__}).")
        print("Check the CSV schema, database schema, and backend configuration.")
        print("Detailed exception contents are suppressed to avoid exposing data.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
