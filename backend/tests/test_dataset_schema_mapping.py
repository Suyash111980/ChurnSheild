from app.repositories import dataset_repository
from app.repositories import learner_repository, prediction_repository
from app.services import dataset_service
from app.services import learner_service


class FakeLearnerQuery:
    def __init__(self):
        self.table_name = None
        self.records = None
        self.conflict = None
        self.columns = None
        self.filters = []

    def table(self, name):
        self.table_name = name
        return self

    def upsert(self, records, *, on_conflict):
        self.records = records
        self.conflict = on_conflict
        return self

    def select(self, columns, **_kwargs):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args):
        return self

    def execute(self):
        return type("Response", (), {"data": [{
            "id": "learner-uuid",
            "dataset_id": "dataset-uuid",
            "external_learner_id": "00123",
            "code_module": "AAA",
            "code_presentation": "2014J",
        }]})()


def test_dataset_processing_maps_oulad_id_to_deployed_database_column():
    source = {
        "id_student": "00123",
        "code_module": "AAA",
        "code_presentation": "2014J",
    }

    payload = dataset_service._learner_payload(source, "dataset-uuid")

    assert payload["external_learner_id"] == "00123"
    assert "id_student" not in payload
    assert payload["dataset_id"] == "dataset-uuid"
    assert dataset_service._source_key(payload) == ("00123", "AAA", "2014J")
    assert dataset_service._source_key(source) == ("00123", "AAA", "2014J")


def test_learner_upsert_uses_migration_005_conflict_key(monkeypatch):
    fake = FakeLearnerQuery()
    monkeypatch.setattr(dataset_repository, "supabase", fake)
    payload = {
        "dataset_id": "dataset-uuid",
        "external_learner_id": "00123",
        "code_module": "AAA",
        "code_presentation": "2014J",
    }

    result = dataset_repository.upsert_learners([payload])

    assert result[0]["external_learner_id"] == "00123"
    assert fake.table_name == "learners"
    assert fake.conflict == "dataset_id,external_learner_id,code_module,code_presentation"
    assert "external_learner_id" in fake.columns


def test_learner_and_prediction_reads_use_deployed_identifier_with_api_alias(monkeypatch):
    fake = FakeLearnerQuery()
    monkeypatch.setattr(learner_repository, "supabase", fake)

    learner_repository.list_learners(
        dataset_id="dataset-uuid", limit=10, offset=0, id_student="00123"
    )

    assert fake.columns == "*"
    assert ("external_learner_id", "00123") in fake.filters
    assert "id_student:external_learner_id" in prediction_repository.PREDICTION_SELECT
    assert learner_service._with_api_source_identifier(
        {"external_learner_id": "00123"}
    )["id_student"] == "00123"

