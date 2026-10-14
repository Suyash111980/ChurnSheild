"""Load a trusted local Phase 3 artifact and predict withdrawal risk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from ml.src.features.model_schema import IDENTIFIER_COLUMNS, validate_feature_frame


def predict_records(records: pd.DataFrame, artifact_dir: str | Path) -> pd.DataFrame:
    """Return class and probability predictions without fitting or retraining."""
    directory = Path(artifact_dir).expanduser().resolve()
    model_path = directory / "random_forest_pipeline.joblib"
    metadata_path = directory / "metadata.json"
    if not model_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Expected model and metadata artifacts in {directory}")
    if records.empty:
        return pd.DataFrame(columns=[*IDENTIFIER_COLUMNS, "predicted_class", "withdrawal_risk_probability", "model_version"])
    validated = validate_feature_frame(records)
    model = joblib.load(model_path)  # Artifacts must be generated locally by this project.
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    probabilities = model.predict_proba(validated)[:, 1]
    threshold = float(metadata["threshold"])
    result = records.loc[:, [column for column in IDENTIFIER_COLUMNS if column in records.columns]].reset_index(drop=True).copy()
    result["predicted_class"] = (probabilities >= threshold).astype(int)
    result["withdrawal_risk_probability"] = probabilities.astype(float)
    result["model_version"] = metadata["model_version"]
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="CSV of Phase 2 prepared feature rows")
    parser.add_argument("--artifact-dir", type=Path, required=True, help="One versioned local artifact directory")
    parser.add_argument("--output", type=Path, help="Optional output CSV; otherwise print predictions")
    args = parser.parse_args(argv)
    if not args.data.is_file():
        parser.error(f"Input CSV not found: {args.data}")
    predictions = predict_records(pd.read_csv(args.data), args.artifact_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(args.output, index=False)
        print(f"Predictions written to {args.output}")
    else:
        print(predictions.to_csv(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
