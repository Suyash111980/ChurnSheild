"""Isolated FastAPI-level tests for dataset ownership and prediction reads.

The stateful store is a contract fake: it exercises real routes, parser,
service orchestration and response schemas without Supabase/PostgREST.
"""

import csv
import io
from threading import Thread
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi import Header
from fastapi.testclient import TestClient

from app.api.dependencies.datasets import require_admin_workspace
from app.integrations.feature_contract import feature_columns
from app.integrations.ml_loader import ModelArtifactError
from app.main import app
from app.repositories import dataset_repository, prediction_repository
from app.services import dataset_service, prediction_service


OWNER_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OWNER_B = "22222222-2222-4222-8222-222222222222"
WORKSPACE_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REQUEST_TIMEOUT_SECONDS = 10


def prepared_csv(student_ids=("00123",)) -> bytes:
    fields = ["id_student", "code_module", "code_presentation", *feature_columns(), "target_withdrawn", "final_result"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(dict.fromkeys(fields)))
    writer.writeheader()
    for student_id in student_ids:
        row = {
            "id_student": student_id,
            "code_module": "AAA",
            "code_presentation": "2014J",
            "target_withdrawn": "1",
            "final_result": "Withdrawn",
        }
        row.update({column: "1" for column in feature_columns() if column not in row})
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


class StatefulStore:
    def __init__(self):
        self.datasets = {}
        self.learners = {}
        self.features = {}
        self.predictions = {}

    def create_dataset(self, payload):
        record = {
            **payload,
            "id": str(uuid4()),
            "uploaded_at": "2026-10-17T00:00:00+00:00",
            "updated_at": "2026-10-17T00:00:00+00:00",
        }
        self.datasets[record["id"]] = record
        return record.copy()

    def get_owned_dataset(self, dataset_id, owner_id, workspace_id):
        record = self.datasets.get(dataset_id)
        if record and record["owner_id"] == owner_id and record["workspace_id"] == workspace_id:
            return record.copy()
        return None

    def update_owned_dataset(self, dataset_id, owner_id, workspace_id, changes):
        record = self.get_owned_dataset(dataset_id, owner_id, workspace_id)
        if record is None:
            return None
        self.datasets[dataset_id].update(changes)
        return self.datasets[dataset_id].copy()

    def upsert_learners(self, records):
        result = []
        for record in records:
            key = (record["dataset_id"], record["external_learner_id"], record["code_module"], record["code_presentation"])
            learner_id = str(uuid5(UUID(record["dataset_id"]), "|".join(key[1:])))
            saved = {**record, "id": learner_id}
            self.learners[key] = saved
            result.append(saved.copy())
        return result

    def upsert_features(self, records):
        for record in records:
            self.features[(record["learner_id"], record["as_of_date"])] = dict(record)

    def upsert_predictions(self, records):
        result = []
        for record in records:
            key = (record["learner_id"], record["model_version"])
            saved = {**self.predictions.get(key, {}), **record}
            saved.setdefault("id", str(uuid4()))
            saved.setdefault("created_at", record.get("created_at"))
            self.predictions[key] = saved
            result.append(saved.copy())
        return result

    def prediction_rows(self, dataset_id):
        learner_by_id = {row["id"]: row for row in self.learners.values() if row["dataset_id"] == dataset_id}
        return [
            {**prediction, "learners": {
                "id": learner["id"],
                "id_student": learner["external_learner_id"],
                "code_module": learner["code_module"],
                "code_presentation": learner["code_presentation"],
                "dataset_id": learner["dataset_id"],
            }}
            for prediction in self.predictions.values()
            if prediction["learner_id"] in learner_by_id
            for learner in [learner_by_id[prediction["learner_id"]]]
        ]


@pytest.fixture
def api_store(monkeypatch):
    store = StatefulStore()
    monkeypatch.setattr(dataset_repository, "supabase", store)
    monkeypatch.setattr(prediction_repository, "supabase", store)
    monkeypatch.setattr(dataset_repository, "create_dataset", store.create_dataset)
    monkeypatch.setattr(dataset_repository, "get_owned_dataset", store.get_owned_dataset)
    monkeypatch.setattr(dataset_repository, "update_owned_dataset", store.update_owned_dataset)
    monkeypatch.setattr(dataset_repository, "upsert_learners", store.upsert_learners)
    monkeypatch.setattr(dataset_repository, "upsert_features", store.upsert_features)
    monkeypatch.setattr(dataset_repository, "upsert_predictions", store.upsert_predictions)
    monkeypatch.setattr(
        dataset_service, "explain_records",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("explainer unavailable in API contract test")),
    )
    monkeypatch.setattr(dataset_service, "recommend_records", lambda rows: [[] for _ in rows])
    monkeypatch.setattr(
        prediction_repository,
        "list_predictions",
        lambda *, dataset_id, **_filters: SimpleNamespace(
            data=store.prediction_rows(dataset_id), count=len(store.prediction_rows(dataset_id))
        ),
    )
    monkeypatch.setattr(
        prediction_service,
        "attach_student_names",
        lambda rows: [{**row, "student_name": None} for row in rows],
    )

    def test_workspace(x_test_user: str = Header(...)):
        workspace = WORKSPACE_A if x_test_user == OWNER_A else WORKSPACE_B
        return {"id": x_test_user, "app_role": "admin", "workspace_id": workspace}

    app.dependency_overrides.clear()
    app.dependency_overrides[require_admin_workspace] = test_workspace
    yield store
    app.dependency_overrides.clear()


def _auth_header(owner=OWNER_A):
    return {"X-Test-User": owner}


def _upload(client, owner=OWNER_A, *, path="/api/v1/datasets/upload", data=None):
    return client.post(
        path,
        headers=_auth_header(owner),
        data=data or {},
        files={"file": ("prepared.csv", prepared_csv(), "text/csv")},
    )


def _bounded_request(request):
    """Run an in-process ASGI request with a hard test timeout, not a sleep."""
    result = []
    error = []

    def run_request():
        try:
            result.append(request())
        except BaseException as exc:
            error.append(exc)

    worker = Thread(target=run_request, daemon=True)
    worker.start()
    worker.join(REQUEST_TIMEOUT_SECONDS)
    assert not worker.is_alive(), (
        f"In-process ASGI request exceeded {REQUEST_TIMEOUT_SECONDS} seconds"
    )
    if error:
        raise error[0]
    assert result, "In-process ASGI request completed without a response"
    return result[0]


def test_upload_persists_scoped_predictions_and_api_reads_them(api_store, monkeypatch):
    monkeypatch.setattr(
        dataset_service,
        "predict_records",
        lambda records, *, record_ids: [
            {"record_id": record_ids[index], "model_version": "approved-test-v1", "risk_probability": 0.73,
             "risk_category": "high", "predicted_at": "2026-10-17T00:00:00+00:00"}
            for index, _record in enumerate(records)
        ],
    )
    client = TestClient(app)
    uploaded = _bounded_request(lambda: _upload(client))
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    dataset_id = body["data"]["id"]
    assert body["data"]["owner_id"] == OWNER_A
    assert api_store.datasets[dataset_id]["workspace_id"] == WORKSPACE_A
    assert body["validation"]["descriptive_compatible"] is True
    assert body["validation"]["errors"] == []
    assert body["validation"]["prediction_state"] == "available"
    assert len(api_store.learners) == 1
    learner = next(iter(api_store.learners.values()))
    assert learner["dataset_id"] == dataset_id

    dataset_readback = _bounded_request(lambda: client.get(
        f"/api/v1/datasets/{dataset_id}", headers=_auth_header()
    ))
    assert dataset_readback.status_code == 200, dataset_readback.text
    assert dataset_readback.json()["id"] == dataset_id
    assert dataset_readback.json()["status"] == "processed"

    response = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={dataset_id}", headers=_auth_header()
    ))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == result["count"] == 1
    assert result["data"][0]["learner_id"] == learner["id"]
    assert result["data"][0]["model_version"] == "approved-test-v1"
    assert result["data"][0]["risk_probability"] == 0.73
    assert result["data"][0]["learners"]["dataset_id"] == dataset_id

    forbidden_dataset = _bounded_request(
        lambda: client.get(f"/api/v1/datasets/{dataset_id}", headers=_auth_header(OWNER_B))
    )
    forbidden_predictions = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={dataset_id}", headers=_auth_header(OWNER_B)
    ))
    assert forbidden_dataset.status_code == 404
    assert forbidden_predictions.status_code == 404


def test_upload_reports_approval_gate_failure_without_prediction(api_store, monkeypatch):
    def approval_disabled(_records, *, record_ids):
        raise ModelArtifactError("inference disabled")

    monkeypatch.setattr(dataset_service, "predict_records", approval_disabled)
    client = TestClient(app)
    uploaded = _bounded_request(lambda: _upload(client))
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["validation"]["prediction_state"] == "unavailable"
    assert api_store.predictions == {}

    dataset_id = uploaded.json()["data"]["id"]
    response = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={dataset_id}", headers=_auth_header()
    ))
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_reprocessing_identical_file_is_idempotent_and_smaller_file_leaves_stale_rows(api_store, monkeypatch):
    def approved(records, *, record_ids):
        return [
            {"record_id": record_ids[index], "model_version": "approved-test-v1", "risk_probability": 0.4,
             "risk_category": "medium", "predicted_at": "2026-10-17T00:00:00+00:00"}
            for index, _record in enumerate(records)
        ]

    monkeypatch.setattr(dataset_service, "predict_records", approved)
    client = TestClient(app)
    initial = _bounded_request(lambda: client.post(
        "/api/v1/datasets/upload", headers=_auth_header(),
        files={"file": ("prepared.csv", prepared_csv(("00123", "00456")), "text/csv")},
    ))
    assert initial.status_code == 201, initial.text
    dataset_id = initial.json()["data"]["id"]
    route = f"/api/v1/datasets/{dataset_id}/reprocess"

    same = _bounded_request(lambda: client.post(
        route, headers=_auth_header(),
        files={"file": ("prepared.csv", prepared_csv(("00123", "00456")), "text/csv")},
    ))
    assert same.status_code == 202, same.text
    assert len(api_store.learners) == 2
    assert len(api_store.predictions) == 2

    smaller = _bounded_request(lambda: client.post(
        route, headers=_auth_header(),
        files={"file": ("prepared.csv", prepared_csv(("00123",)), "text/csv")},
    ))
    assert smaller.status_code == 202, smaller.text
    assert len(api_store.learners) == 2
    assert len(api_store.predictions) == 2
    readback = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={dataset_id}", headers=_auth_header()
    ))
    assert readback.status_code == 200
    assert readback.json()["total"] == 2
