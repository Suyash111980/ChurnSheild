from types import SimpleNamespace

import joblib
import pytest

from app.core.config import settings
from app.integrations import ml_loader


def test_missing_model_artifact_has_safe_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "model_path", str(tmp_path / "missing.joblib"))
    with pytest.raises(ml_loader.ModelArtifactError, match="does not exist"):
        ml_loader.get_model()


def test_incompatible_model_artifact_has_safe_failure(monkeypatch, tmp_path):
    path = tmp_path / "not-a-model.joblib"
    joblib.dump({"some": "data"}, path)
    monkeypatch.setattr(settings, "model_path", str(path))
    with pytest.raises(ml_loader.ModelArtifactError, match="predict_proba"):
        ml_loader.get_model()


def test_model_load_is_cached_by_artifact_version(monkeypatch, tmp_path):
    from sklearn.dummy import DummyClassifier

    path = tmp_path / "model.joblib"
    model = DummyClassifier(strategy="prior").fit([[0], [1]], [0, 1])
    joblib.dump(model, path)
    monkeypatch.setattr(settings, "model_path", str(path))
    ml_loader._load_model.cache_clear()

    assert ml_loader.get_model() is ml_loader.get_model()


def test_model_feature_names_and_order_are_checked():
    model = SimpleNamespace(feature_names_in_=["clicks", "credits"])
    ml_loader.validate_model_features(model, ["clicks", "credits"])
    with pytest.raises(ml_loader.ModelFeatureError):
        ml_loader.validate_model_features(model, ["credits", "clicks"])
    with pytest.raises(ml_loader.ModelFeatureError):
        ml_loader.validate_model_features(model, ["clicks", "credits", "student_name"])


def test_display_name_is_never_a_model_feature_even_without_feature_metadata():
    model = SimpleNamespace(n_features_in_=2)
    with pytest.raises(ml_loader.ModelFeatureError, match="Display names"):
        ml_loader.validate_model_features(model, ["clicks", "student_name"])


def test_model_feature_width_is_checked_when_names_unavailable():
    model = SimpleNamespace(n_features_in_=2)
    ml_loader.validate_model_features(model, ["a", "b"])
    with pytest.raises(ml_loader.ModelFeatureError):
        ml_loader.validate_model_features(model, ["a"])


def test_inference_requires_an_explicit_exact_model_version(monkeypatch, tmp_path):
    path = tmp_path / "model.joblib"
    path.with_suffix(".metadata.json").write_text(
        '{"model_version":"provisional-candidate"}', encoding="utf-8"
    )

    monkeypatch.setattr(settings, "model_approved_version", "")
    with pytest.raises(ml_loader.ModelArtifactError, match="disabled"):
        ml_loader.require_approved_model_version(path)

    monkeypatch.setattr(settings, "model_approved_version", "approved-model-1.0.0")
    with pytest.raises(ml_loader.ModelArtifactError, match="not approved"):
        ml_loader.require_approved_model_version(path)

    monkeypatch.setattr(settings, "model_approved_version", "provisional-candidate")
    assert ml_loader.require_approved_model_version(path) == "provisional-candidate"


def test_explanation_generation_obeys_the_same_approval_gate(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ml_loader, "require_approved_model_version",
        lambda: (_ for _ in ()).throw(ml_loader.ModelArtifactError("not approved")),
    )
    monkeypatch.setattr(ml_loader, "get_model", lambda: calls.append("model") or object())

    with pytest.raises(ml_loader.ModelArtifactError, match="not approved"):
        ml_loader.explain_records([{}])
    assert calls == []

