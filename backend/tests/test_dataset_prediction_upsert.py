from types import SimpleNamespace

from app.repositories import dataset_repository


class FakeQuery:
    def __init__(self):
        self.payload = None
        self.conflict = None
        self.selection = None

    def table(self, name):
        assert name == "predictions"
        return self

    def upsert(self, records, *, on_conflict):
        self.payload = records
        self.conflict = on_conflict
        return self

    def select(self, columns):
        self.selection = columns
        return self

    def execute(self):
        return SimpleNamespace(data=self.payload)


def test_prediction_reprocessing_upserts_on_learner_and_model(monkeypatch):
    fake = FakeQuery()
    monkeypatch.setattr(dataset_repository, "supabase", fake)
    record = {
        "learner_id": "learner-uuid",
        "model_version": "model-v1",
        "risk_probability": 0.61,
        "risk_category": "medium",
        "created_at": "2026-10-15T00:00:00+00:00",
    }

    assert dataset_repository.upsert_predictions([record]) == [record]
    assert fake.conflict == "learner_id,model_version"
    assert fake.payload == [record]
    assert "risk_probability" in fake.selection


def test_empty_prediction_batch_skips_database(monkeypatch):
    def fail_if_called():
        raise AssertionError("Database must not be accessed for an empty batch")

    monkeypatch.setattr(dataset_repository, "_client", fail_if_called)
    assert dataset_repository.upsert_predictions([]) == []
