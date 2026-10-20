"""Fake-backed tests for prediction-associated evidence persistence."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.integrations.feature_contract import feature_columns
from app.repositories import dataset_repository
from app.services import dataset_service


DATASET_ID = "dataset-a"
LEARNER_ID = "learner-a"
PREDICTION_ID = "prediction-a"
MODEL_VERSION = "approved-test-v1"


def _features():
    return {
        name: 0 if name == "vle_has_activity_by_cutoff" else 1
        for name in feature_columns()
    }


def _contributions(records):
    return [[
        {"feature_name": name, "contribution": index / 100}
        for index, name in enumerate(feature_columns())
    ] for _ in records]


def test_saved_prediction_receives_validated_explanations_and_qualified_recommendation(monkeypatch):
    writes = {"explanations": [], "recommendations": []}
    monkeypatch.setattr(dataset_service, "explain_records", _contributions)
    monkeypatch.setattr(dataset_service, "recommend_records", lambda _records: [[{
        "rule_id": "no_observed_vle_activity_by_cutoff",
        "action": "Check platform access and offer a supportive check-in.",
        "evidence": {
            "feature": "vle_has_activity_by_cutoff",
            "observed_value": 0,
            "interpretation": "No VLE activity was recorded by the cutoff.",
        },
        "requires_human_review": True,
    }]])
    monkeypatch.setattr(
        dataset_repository, "upsert_explanations",
        lambda payload: writes["explanations"].extend(deepcopy(payload)) or deepcopy(payload),
    )
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda payload, *, dataset_id: writes["recommendations"].extend(
            deepcopy([{**row, "dataset_id": dataset_id} for row in payload])
        ) or {"persisted": deepcopy(payload), "failed_count": 0},
    )

    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()],
        learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{
            "id": PREDICTION_ID, "learner_id": LEARNER_ID,
            "model_version": MODEL_VERSION,
        }],
    )

    assert result["explanations_state"] == "available"
    assert result["explanations_persisted"] == len(feature_columns())
    assert len(writes["explanations"]) == len(feature_columns())
    assert {row["prediction_id"] for row in writes["explanations"]} == {PREDICTION_ID}
    assert [row["feature_name"] for row in writes["explanations"]] == feature_columns()
    assert writes["explanations"][0]["feature_value"] == 1
    assert result["recommendations_state"] == "available"
    recommendation = writes["recommendations"][0]
    assert recommendation["learner_id"] == LEARNER_ID
    assert recommendation["prediction_id"] == PREDICTION_ID
    assert recommendation["rule_id"] == "no_observed_vle_activity_by_cutoff"
    assert recommendation["status"] == "pending"
    assert "vle_has_activity_by_cutoff=0" in recommendation["reason"]
    assert recommendation["dataset_id"] == DATASET_ID


def test_missing_or_wrong_prediction_is_reported_as_auxiliary_failure(monkeypatch):
    monkeypatch.setattr(dataset_service, "explain_records", lambda *_args: pytest.fail("must not explain"))
    monkeypatch.setattr(dataset_service, "recommend_records", lambda *_args: pytest.fail("must not recommend"))
    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()],
        learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{
            "id": PREDICTION_ID, "learner_id": LEARNER_ID,
            "model_version": "different-version",
        }],
    )
    assert result["explanations_state"] == "unavailable"
    assert result["explanations_failed"] == 1
    assert result["recommendations_state"] == "unavailable"
    assert result["recommendations_failed"] == 1


def test_malformed_explanations_do_not_block_recommendation_persistence(monkeypatch):
    writes = []
    malformed = [[{"feature_name": "not_a_model_feature", "contribution": 0.3}]]
    monkeypatch.setattr(dataset_service, "explain_records", lambda _records: malformed)
    monkeypatch.setattr(dataset_service, "recommend_records", lambda _records: [[]])
    monkeypatch.setattr(dataset_repository, "upsert_explanations", lambda _payload: pytest.fail("invalid write"))
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda payload, **_kwargs: writes.extend(payload) or {"persisted": payload, "failed_count": 0},
    )

    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()], learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{"id": PREDICTION_ID, "learner_id": LEARNER_ID, "model_version": MODEL_VERSION}],
    )
    assert result["explanations_state"] == "unavailable"
    assert result["recommendations_state"] == "empty"
    assert writes == []


@pytest.mark.parametrize("corruption", ["prediction", "feature", "missing", "duplicate"])
def test_explanation_upsert_response_must_match_every_written_association(monkeypatch, corruption):
    payload_rows = []
    monkeypatch.setattr(dataset_service, "explain_records", _contributions)
    monkeypatch.setattr(dataset_service, "recommend_records", lambda records: [[] for _ in records])

    def invalid_upsert(payload):
        payload_rows.extend(deepcopy(payload))
        returned = deepcopy(payload)
        if corruption == "prediction":
            returned[0]["prediction_id"] = "another-prediction"
        elif corruption == "feature":
            returned[0]["feature_name"] = "another-feature"
        elif corruption == "missing":
            returned.pop()
        else:
            returned[-1] = deepcopy(returned[0])
        return returned

    monkeypatch.setattr(dataset_repository, "upsert_explanations", invalid_upsert)
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda *_args, **_kwargs: pytest.fail("no recommendation write expected"),
    )

    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()],
        learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{
            "id": PREDICTION_ID, "learner_id": LEARNER_ID,
            "model_version": MODEL_VERSION,
        }],
    )

    assert len(payload_rows) == len(feature_columns())
    assert result["explanations_state"] == "unavailable"
    assert result["explanations_persisted"] == 0
    assert result["explanations_failed"] == 1
    assert result["recommendations_state"] == "empty"


def test_mismatched_saved_prediction_association_is_reported_as_auxiliary_failure(monkeypatch):
    monkeypatch.setattr(dataset_service, "explain_records", lambda *_args: pytest.fail("must not explain"))
    monkeypatch.setattr(dataset_service, "recommend_records", lambda *_args: pytest.fail("must not recommend"))
    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()],
        learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{
            "id": PREDICTION_ID, "learner_id": LEARNER_ID,
            "model_version": "different-version",
        }],
    )
    assert result["explanations_state"] == "unavailable"
    assert result["explanations_failed"] == 1
    assert result["recommendations_state"] == "unavailable"
    assert result["recommendations_failed"] == 1


def test_recommendation_evidence_must_match_the_measured_feature_value(monkeypatch):
    monkeypatch.setattr(dataset_service, "explain_records", _contributions)
    monkeypatch.setattr(dataset_service, "recommend_records", lambda _records: [[{
        "rule_id": "no_observed_vle_activity_by_cutoff",
        "action": "Check platform access.",
        "evidence": {
            "feature": "vle_has_activity_by_cutoff",
            "observed_value": 1,
            "interpretation": "An inconsistent observation.",
        },
        "requires_human_review": True,
    }]])
    monkeypatch.setattr(dataset_repository, "upsert_explanations", lambda records: records)
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda *_args, **_kwargs: pytest.fail("inconsistent evidence must not persist"),
    )

    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID, feature_records=[_features()], learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{"id": PREDICTION_ID, "learner_id": LEARNER_ID, "model_version": MODEL_VERSION}],
    )
    assert result["recommendations_state"] == "unavailable"


@pytest.mark.parametrize("association", ["learner_id", "prediction_id"])
def test_recommendation_learner_prediction_mismatch_is_rejected_before_persistence(monkeypatch, association):
    mismatched = {
        "learner_id": "another-learner",
        "prediction_id": "another-prediction",
    }
    monkeypatch.setattr(dataset_service, "explain_records", _contributions)
    monkeypatch.setattr(dataset_service, "recommend_records", lambda _records: [[{
        "rule_id": "no_observed_vle_activity_by_cutoff",
        "action": "Check platform access.",
        association: mismatched[association],
        "evidence": {
            "feature": "vle_has_activity_by_cutoff",
            "observed_value": 0,
            "interpretation": "No VLE activity was recorded by cutoff.",
        },
        "requires_human_review": True,
    }]])
    monkeypatch.setattr(dataset_repository, "upsert_explanations", lambda rows: rows)
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda *_args, **_kwargs: pytest.fail("mismatched recommendation must not persist"),
    )

    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()],
        learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{
            "id": PREDICTION_ID, "learner_id": LEARNER_ID,
            "model_version": MODEL_VERSION,
        }],
    )

    assert result["recommendations_state"] == "unavailable"
    assert result["recommendations_failed"] == 1


def test_missing_recommendation_rule_id_is_rejected_before_persistence(monkeypatch):
    monkeypatch.setattr(dataset_service, "explain_records", _contributions)
    monkeypatch.setattr(dataset_service, "recommend_records", lambda _records: [[{
        "action": "Check platform access.",
        "evidence": {
            "feature": "vle_has_activity_by_cutoff",
            "observed_value": 0,
            "interpretation": "No VLE activity was recorded by cutoff.",
        },
        "requires_human_review": True,
    }]])
    monkeypatch.setattr(dataset_repository, "upsert_explanations", lambda rows: rows)
    monkeypatch.setattr(
        dataset_repository, "upsert_recommendations",
        lambda *_args, **_kwargs: pytest.fail("missing rule ID must be rejected before persistence"),
    )

    result = dataset_service._persist_prediction_evidence(
        dataset_id=DATASET_ID,
        feature_records=[_features()],
        learner_ids=[LEARNER_ID],
        model_versions=[MODEL_VERSION],
        saved_predictions=[{
            "id": PREDICTION_ID, "learner_id": LEARNER_ID,
            "model_version": MODEL_VERSION,
        }],
    )

    assert result["recommendations_state"] == "unavailable"
    assert result["recommendations_failed"] == 1


class FakeRecommendationClient:
    def __init__(self, rows=None, *, readback_override=None):
        self.rows = deepcopy(rows or [])
        self.learners = {
            LEARNER_ID: DATASET_ID,
            "learner-b": "dataset-b",
        }
        self.mode = None
        self.filters = {}
        self.write_args = []
        self.readback_override = readback_override

    def table(self, name):
        assert name == "recommendations"
        return self

    def upsert(self, records, *, on_conflict, ignore_duplicates):
        self.mode = "upsert"
        self.filters = {}
        self.write_args.append((on_conflict, ignore_duplicates, deepcopy(records)))
        for record in records:
            key = (record.get("prediction_id"), record.get("rule_id"))
            existing = next((row for row in self.rows if (
                row.get("prediction_id"), row.get("rule_id")
            ) == key), None)
            if existing is not None and ignore_duplicates:
                continue
            saved = {**deepcopy(record), "id": f"{key[0]}:{key[1]}",
                     "created_at": "2026-10-18T00:00:00+00:00",
                     "updated_at": record.get("updated_at")}
            if existing is not None:
                self.rows.remove(existing)
            self.rows.append(saved)
        return self

    def select(self, *_args, **_kwargs):
        self.mode = "read"
        self.filters = {}
        return self

    def in_(self, field, values):
        self.filters[field] = set(values)
        return self

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def execute(self):
        if self.mode == "upsert":
            # Ignore-duplicates may return inserted rows only; caller must read back.
            return SimpleNamespace(data=[])
        rows = []
        for row in self.rows:
            learner_dataset = self.learners.get(row.get("learner_id"))
            if row.get("prediction_id") not in self.filters.get("prediction_id", set()):
                continue
            if row.get("rule_id") not in self.filters.get("rule_id", set()):
                continue
            if learner_dataset != self.filters.get("learners.dataset_id"):
                continue
            rows.append({**deepcopy(row), "learners": {
                "id": row.get("learner_id"), "dataset_id": learner_dataset,
            }})
        if self.readback_override is not None:
            rows = self.readback_override(rows)
        return SimpleNamespace(data=deepcopy(rows))


def _candidate(prediction_id=PREDICTION_ID, rule_id="rule-a", **overrides):
    return {
        "learner_id": LEARNER_ID,
        "prediction_id": prediction_id,
        "rule_id": rule_id,
        "action": "Offer a check-in",
        "reason": "Rule: measured evidence.",
        "status": "pending",
        **overrides,
    }


@pytest.mark.parametrize("status", ["pending", "in_progress", "completed", "dismissed"])
def test_recommendation_retry_uses_ignore_duplicate_upsert_and_preserves_status(monkeypatch, status):
    fake = FakeRecommendationClient()
    monkeypatch.setattr(dataset_repository, "supabase", fake)

    first = dataset_repository.upsert_recommendations(
        [_candidate(reason="Original persisted rationale.")], dataset_id=DATASET_ID
    )
    assert len(first["persisted"]) == 1
    if status != "pending":
        fake.rows[0]["status"] = status

    result = dataset_repository.upsert_recommendations(
        [_candidate(reason="Retry rationale must not replace the saved row.")],
        dataset_id=DATASET_ID,
    )
    assert len(fake.rows) == 1
    assert result["failed_count"] == 0
    assert result["persisted"][0]["status"] == status
    assert result["persisted"][0]["reason"] == "Original persisted rationale."
    assert fake.write_args[0][:2] == ("prediction_id,rule_id", True)
    assert fake.filters["learners.dataset_id"] == DATASET_ID


def test_recommendation_identity_separates_predictions_and_rules(monkeypatch):
    fake = FakeRecommendationClient()
    monkeypatch.setattr(dataset_repository, "supabase", fake)

    result = dataset_repository.upsert_recommendations(
        [
            _candidate(prediction_id="prediction-a", rule_id="rule-a"),
            _candidate(prediction_id="prediction-b", rule_id="rule-a"),
            _candidate(prediction_id="prediction-a", rule_id="rule-b"),
        ],
        dataset_id=DATASET_ID,
    )

    assert len(fake.rows) == len(result["persisted"]) == 3
    assert {(row["prediction_id"], row["rule_id"]) for row in fake.rows} == {
        ("prediction-a", "rule-a"), ("prediction-b", "rule-a"),
        ("prediction-a", "rule-b"),
    }


def test_historical_null_rule_recommendation_is_preserved(monkeypatch):
    historical = {
        "id": "historical", "learner_id": LEARNER_ID,
        "prediction_id": None, "rule_id": None, "action": "Old action",
        "reason": "Historical reason", "status": "completed",
    }
    fake = FakeRecommendationClient([historical])
    monkeypatch.setattr(dataset_repository, "supabase", fake)

    result = dataset_repository.upsert_recommendations(
        [_candidate()], dataset_id=DATASET_ID
    )

    assert historical in fake.rows
    assert len(fake.rows) == 2
    assert result["failed_count"] == 0


@pytest.mark.parametrize("corruption", ["missing", "wrong_learner", "other_dataset", "duplicate"])
def test_recommendation_scoped_readback_rejects_unconfirmed_rows(monkeypatch, corruption):
    def corrupt(rows):
        if corruption == "missing":
            return []
        if corruption == "wrong_learner":
            return [{**rows[0], "learner_id": "learner-b", "learners": {
                "id": "learner-b", "dataset_id": DATASET_ID,
            }}]
        if corruption == "other_dataset":
            return [{**rows[0], "learners": {
                "id": LEARNER_ID, "dataset_id": "dataset-b",
            }}]
        return [rows[0], deepcopy(rows[0])]

    fake = FakeRecommendationClient(readback_override=corrupt)
    monkeypatch.setattr(dataset_repository, "supabase", fake)

    result = dataset_repository.upsert_recommendations(
        [_candidate()], dataset_id=DATASET_ID
    )

    assert result["persisted"] == []
    assert result["failed_count"] == 1


def test_recommendation_repository_rejects_missing_rule_id_before_write(monkeypatch):
    fake = FakeRecommendationClient()
    monkeypatch.setattr(dataset_repository, "supabase", fake)

    result = dataset_repository.upsert_recommendations(
        [_candidate(rule_id="")], dataset_id=DATASET_ID
    )

    assert result == {"persisted": [], "failed_count": 1}
    assert fake.write_args == []


def test_explanation_repository_uses_existing_prediction_feature_unique_key(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.rows = {}
            self.payload = []
            self.conflict = None

        def table(self, name):
            assert name == "risk_explanations"
            return self

        def upsert(self, records, *, on_conflict):
            self.conflict = on_conflict
            self.payload = []
            for record in records:
                key = (record["prediction_id"], record["feature_name"])
                saved = {**self.rows.get(key, {}), **record, "id": f"{key[0]}:{key[1]}"}
                self.rows[key] = saved
                self.payload.append(saved)
            return self

        def select(self, _columns):
            return self

        def execute(self):
            return SimpleNamespace(data=deepcopy(self.payload))

    fake = FakeClient()
    monkeypatch.setattr(dataset_repository, "supabase", fake)
    key = {"prediction_id": PREDICTION_ID, "feature_name": "studied_credits"}
    dataset_repository.upsert_explanations([{**key, "feature_value": 90, "contribution": 0.2}])
    dataset_repository.upsert_explanations([{**key, "feature_value": 90, "contribution": 0.4}])

    assert fake.conflict == "prediction_id,feature_name"
    assert len(fake.rows) == 1
    assert next(iter(fake.rows.values()))["contribution"] == 0.4
