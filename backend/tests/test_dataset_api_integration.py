"""Isolated FastAPI-level tests for dataset ownership and prediction reads.

The stateful store is a contract fake: it exercises real routes, parser,
service orchestration and response schemas without Supabase/PostgREST.
"""

import asyncio
import csv
import io
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi import Header
import httpx

from app.api.dependencies.datasets import require_admin_workspace
from app.core.config import settings
from app.integrations.feature_contract import feature_columns
from app.integrations.ml_loader import ModelArtifactError
from app.main import app
from app.repositories import dataset_repository, learner_repository, prediction_repository
from app.services import dataset_service, prediction_service


OWNER_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OWNER_B = "22222222-2222-4222-8222-222222222222"
WORKSPACE_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REQUEST_TIMEOUT_SECONDS = 10

# The default Proactor event loop stalls while initializing its self-pipe in
# this Windows sandbox. Selector policy supports the local ASGITransport tests.


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

    def dataset_source_keys(self, dataset_id):
        return {
            (row["external_learner_id"], row["code_module"], row["code_presentation"])
            for row in self.learners.values()
            if row["dataset_id"] == dataset_id
        }

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
    monkeypatch.setattr(dataset_repository, "get_dataset_source_keys", store.dataset_source_keys)
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

    async def test_workspace(x_test_user: str = Header(...)):
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


class LocalASGIClient:
    """Use httpx ASGITransport directly, avoiding TestClient's Windows portal socket."""

    async def _async_request(self, method, path, **kwargs):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await asyncio.wait_for(
                client.request(method, path, **kwargs), timeout=REQUEST_TIMEOUT_SECONDS
            )

    def request(self, method, path, **kwargs):
        return asyncio.run(self._async_request(method, path, **kwargs))

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


def _bounded_request(request):
    """Execute the local ASGI request under its asyncio timeout."""
    return request()


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
    client = LocalASGIClient()
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


def test_upload_runs_approved_model_and_saves_its_prediction(api_store):
    """Exercise the real approved artifact through the upload and read APIs."""
    client = LocalASGIClient()
    uploaded = _bounded_request(lambda: _upload(client))
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    dataset_id = body["data"]["id"]
    assert body["validation"]["prediction_state"] == "available"
    assert body["validation"]["predictions_persisted"] == 1
    assert body["validation"]["prediction_rows_skipped"] == 0

    saved = list(api_store.predictions.values())
    assert len(saved) == 1
    assert saved[0]["model_version"] == settings.model_approved_version
    assert 0.0 <= saved[0]["risk_probability"] <= 1.0
    assert saved[0]["risk_category"] in {"low", "medium", "high"}

    readback = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={dataset_id}", headers=_auth_header()
    ))
    assert readback.status_code == 200, readback.text
    assert readback.json()["total"] == 1
    assert readback.json()["data"][0]["risk_probability"] == saved[0]["risk_probability"]


def test_course_insights_api_returns_dataset_scoped_saved_risk(api_store, monkeypatch):
    dataset = api_store.create_dataset({
        "owner_id": OWNER_A,
        "workspace_id": WORKSPACE_A,
        "dataset_name": "Course test",
        "filename": "course.csv",
        "status": "processed",
        "row_count": 2,
    })
    monkeypatch.setattr(learner_repository, "supabase", api_store)
    monkeypatch.setattr(learner_repository, "list_course_insight_rows", lambda _dataset_id: [
        {"code_module": "AAA", "code_presentation": "2014J", "latest_risk_probability": 0.8, "latest_risk_category": "high"},
        {"code_module": "AAA", "code_presentation": "2014J", "latest_risk_probability": 0.2, "latest_risk_category": "low"},
    ])

    response = _bounded_request(lambda: LocalASGIClient().get(
        f"/api/v1/courses/insights?dataset_id={dataset['id']}", headers=_auth_header()
    ))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dataset_id"] == dataset["id"]
    assert body["learner_course_records"] == 2
    assert body["courses"][0]["high_risk_count"] == 1
    assert body["courses"][0]["average_risk_probability"] == 0.5
    assert body["weekly_activity_available"] is False


def test_upload_reports_approval_gate_failure_without_prediction(api_store, monkeypatch):
    def approval_disabled(_records, *, record_ids):
        raise ModelArtifactError("inference disabled")

    monkeypatch.setattr(dataset_service, "predict_records", approval_disabled)
    client = LocalASGIClient()
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


def test_changed_reprocessing_creates_a_new_dataset_and_preserves_original_rows(api_store, monkeypatch):
    def approved(records, *, record_ids):
        return [
            {"record_id": record_ids[index], "model_version": "approved-test-v1", "risk_probability": 0.4,
             "risk_category": "medium", "predicted_at": "2026-10-17T00:00:00+00:00"}
            for index, _record in enumerate(records)
        ]

    monkeypatch.setattr(dataset_service, "predict_records", approved)
    client = LocalASGIClient()
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

    revised = _bounded_request(lambda: client.post(
        route, headers=_auth_header(),
        files={"file": ("prepared.csv", prepared_csv(("00123",)), "text/csv")},
    ))
    assert revised.status_code == 202, revised.text
    revised_dataset_id = revised.json()["data"]["id"]
    assert revised_dataset_id != dataset_id
    assert revised.json()["validation"]["source_revision_created"] is True
    assert len(api_store.learners) == 3
    assert len(api_store.predictions) == 3
    old_readback = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={dataset_id}", headers=_auth_header()
    ))
    new_readback = _bounded_request(lambda: client.get(
        f"/api/v1/predictions?dataset_id={revised_dataset_id}", headers=_auth_header()
    ))
    assert old_readback.status_code == 200
    assert old_readback.json()["total"] == 2
    assert new_readback.status_code == 200
    assert new_readback.json()["total"] == 1
