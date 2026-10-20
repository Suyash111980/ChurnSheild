"""Optional local SHAP explanations aligned to the canonical input schema."""

from __future__ import annotations

from typing import Any

import numpy as np

from ml.src.features.build_features import validate_feature_frame


class ExplanationUnavailable(RuntimeError):
    """An explanation could not be produced reliably for this artifact/input."""


def explain_with_shap(pipeline, records) -> list[list[dict[str, Any]]]:
    """Return positive-class contributions grouped back to canonical features."""
    try:
        import shap

        features = validate_feature_frame(records)
        preprocessor = pipeline.named_steps["preprocessor"]
        classifier = pipeline.named_steps["classifier"]
        transformed = preprocessor.transform(features)
        explainer = shap.TreeExplainer(classifier)
        values = explainer.shap_values(transformed)
        class_index = list(classifier.classes_).index(1)
        if isinstance(values, list):
            values = values[class_index]
        else:
            values = np.asarray(values)
            if values.ndim == 3:
                if values.shape[-1] != len(classifier.classes_):
                    raise ValueError("SHAP class axis did not match classifier classes")
                values = values[:, :, class_index]
        values = np.asarray(values, dtype=float)
        names = list(preprocessor.get_feature_names_out())
        if values.shape != (len(features), len(names)) or not np.isfinite(values).all():
            raise ValueError("SHAP output shape or values did not match transformed features")

        # Sum one-hot contributions back to their canonical input feature.
        canonical_by_encoded = {canonical: [] for canonical in features.columns}
        for index, encoded_name in enumerate(names):
            _, _, transformed_name = str(encoded_name).partition("__")
            # SimpleImputer(add_indicator=True) emits
            # ``missingindicator_<canonical-name>`` columns. These are part of
            # the same source feature and should be included in its contribution.
            if transformed_name.startswith("missingindicator_"):
                transformed_name = transformed_name.removeprefix("missingindicator_")
            owner = next((
                name for name in features.columns
                if transformed_name == name or transformed_name.startswith(f"{name}_")
            ), None)
            if owner is None:
                raise ValueError("Transformed feature has no canonical input owner")
            canonical_by_encoded[owner].append(index)
        if sum(map(len, canonical_by_encoded.values())) != len(names) or any(
            not indices for indices in canonical_by_encoded.values()
        ):
            raise ValueError("Transformed SHAP features could not be aligned to canonical inputs")
        results = []
        for row_values in values:
            contributions = [
                {"feature_name": name, "contribution": float(row_values[indices].sum())}
                for name, indices in canonical_by_encoded.items()
            ]
            results.append(sorted(contributions, key=lambda item: abs(item["contribution"]), reverse=True))
        return results
    except Exception as exc:
        raise ExplanationUnavailable("A reliable explanation is unavailable for this model input") from exc
