"""Score a compatible CSV locally with a saved ChurnShield model artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

from ml.src.features.build_features import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
    TARGET_COLUMN,
)
from ml.src.inference.predict import InferenceContractError, predict_records


OUTPUT_COLUMNS = IDENTIFIER_COLUMNS + [
    "risk_probability",
    "risk_category",
    "model_version",
    "predicted_at",
]


def predict_csv(input_path: str | Path, output_path: str | Path, artifact_path: str | Path) -> int:
    """Read feature records and write prediction rows; refuse destructive paths."""
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    artifact = Path(artifact_path).expanduser().resolve()
    if source == destination:
        raise InferenceContractError("Prediction output must not overwrite the input CSV")
    if destination.exists():
        raise InferenceContractError("Prediction output already exists; choose a new output path")
    try:
        frame = pd.read_csv(source, dtype={IDENTIFIER_COLUMNS[0]: "string"})
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError) as exc:
        raise InferenceContractError("Input CSV is missing or could not be parsed") from exc
    if TARGET_COLUMN in frame.columns:
        raise InferenceContractError("Inference input must not contain the training target column")
    required = list(dict.fromkeys(IDENTIFIER_COLUMNS + FEATURE_COLUMNS))
    missing = [column for column in required if column not in frame.columns]
    unexpected = [column for column in frame.columns if column not in required]
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected columns: {', '.join(unexpected)}")
        raise InferenceContractError("Input CSV does not match the inference schema (" + "; ".join(details) + ")")
    identifiers = frame.loc[:, IDENTIFIER_COLUMNS].copy()
    if identifiers.isna().any().any() or identifiers.astype("string").apply(
        lambda column: column.str.strip().eq("").any()
    ).any():
        raise InferenceContractError("Input identifiers must be present and non-empty")
    if identifiers.duplicated(IDENTIFIER_COLUMNS).any():
        raise InferenceContractError("Input rows must be unique by learner, module, and presentation")
    if frame.empty:
        raise InferenceContractError("Input CSV must contain at least one feature record")
    record_ids = identifiers.astype("string").agg("|".join, axis=1).tolist()
    predictions = predict_records(
        frame.loc[:, FEATURE_COLUMNS],
        record_ids=record_ids,
        artifact_path=artifact,
    )
    output = identifiers.reset_index(drop=True).join(pd.DataFrame(predictions).drop(columns="record_id"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.loc[:, OUTPUT_COLUMNS].to_csv(destination, index=False)
    return len(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="CSV with identifiers and canonical feature columns")
    parser.add_argument("--output", required=True, type=Path, help="New CSV path for predictions")
    parser.add_argument("--artifact", type=Path, default=Path("ml/artifacts/churn_model.joblib"))
    args = parser.parse_args(argv)
    try:
        count = predict_csv(args.input, args.output, args.artifact)
    except (InferenceContractError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Scored {count:,} records; predictions written to {args.output.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
