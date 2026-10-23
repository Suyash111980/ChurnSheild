from types import SimpleNamespace

import pandas as pd
import pytest

from app.repositories import dataset_repository
from app.services import dataset_service


def test_processed_dataset_can_be_reprocessed_in_place(monkeypatch):
    frame = pd.DataFrame([{"id_student": "1", "code_module": "AAA", "code_presentation": "2014J"}])
    existing = {
        "id": "dataset-1", "status": "processed",
        "validation_results": {"source_fingerprint": dataset_service._source_fingerprint(frame)},
    }
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *args: existing)
    monkeypatch.setattr(dataset_service, "_update_dataset", lambda *args: existing)
    parsed = SimpleNamespace(frame=frame, report={})
    monkeypatch.setattr(dataset_service, "parse_dataset", lambda *args: parsed)
    expected = {"data": existing, "validation": {"processed_again": True}}
    calls = []

    def process(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(dataset_service, "_process_parsed_dataset", process)

    with pytest.raises(ValueError):
        dataset_service.upload_dataset(
            owner_id="owner", workspace_id="workspace", filename="cohort.csv",
            dataset_name="", content=b"csv", dataset_id="dataset-1",
        )

    result = dataset_service.upload_dataset(
        owner_id="owner", workspace_id="workspace", filename="cohort.csv",
        dataset_name="", content=b"csv", dataset_id="dataset-1", allow_reprocess=True,
    )

    assert result is expected
    assert len(calls) == 1
    assert calls[0]["dataset_id"] == "dataset-1"
    assert calls[0]["initial_record"] is existing


def test_changed_source_is_saved_as_a_new_dataset_without_mutating_old_revision(monkeypatch):
    old_frame = pd.DataFrame([{"id_student": "1", "code_module": "AAA", "code_presentation": "2014J"}])
    new_frame = pd.DataFrame([{"id_student": "2", "code_module": "AAA", "code_presentation": "2014J"}])
    existing = {
        "id": "dataset-old", "status": "processed", "dataset_name": "Cohort",
        "validation_results": {"source_fingerprint": dataset_service._source_fingerprint(old_frame)},
    }
    created = {
        "id": "dataset-new", "status": "uploaded", "owner_id": "owner",
        "workspace_id": "workspace", "dataset_name": "Cohort (updated)",
    }
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *args: existing)
    monkeypatch.setattr(
        dataset_repository, "get_dataset_source_keys",
        lambda _dataset_id: {("1", "AAA", "2014J")},
    )
    monkeypatch.setattr(dataset_service, "parse_dataset", lambda *args: SimpleNamespace(frame=new_frame, report={}))
    monkeypatch.setattr(dataset_repository, "create_dataset", lambda payload: created)
    monkeypatch.setattr(dataset_service, "_process_parsed_dataset", lambda **kwargs: {
        "data": created, "validation": {}, "dataset_id_seen": kwargs["dataset_id"],
    })
    updates = []
    monkeypatch.setattr(dataset_service, "_update_dataset", lambda *args: updates.append(args))

    result = dataset_service.upload_dataset(
        owner_id="owner", workspace_id="workspace", filename="new.csv", dataset_name="",
        content=b"new source", dataset_id="dataset-old", allow_reprocess=True,
    )

    assert result["data"]["id"] == "dataset-new"
    assert result["dataset_id_seen"] == "dataset-new"
    assert result["validation"]["source_revision_created"] is True
    assert updates == []


def test_changed_features_with_identical_membership_reuse_dataset_id(monkeypatch):
    old_frame = pd.DataFrame([{
        "id_student": "00123", "code_module": "AAA", "code_presentation": "2014J",
        "vle_total_clicks_by_cutoff": 12,
    }])
    enriched_frame = pd.DataFrame([{
        "id_student": "00123", "code_module": "AAA", "code_presentation": "2014J",
        "vle_total_clicks_by_cutoff": 12, "registration_by_cutoff": 1,
    }])
    existing = {
        "id": "dataset-1", "status": "processed", "dataset_name": "Cohort",
        "validation_results": {"source_fingerprint": dataset_service._source_fingerprint(old_frame)},
    }
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *args: existing)
    monkeypatch.setattr(dataset_service, "parse_dataset", lambda *args: SimpleNamespace(
        frame=enriched_frame, report={},
    ))
    monkeypatch.setattr(
        dataset_repository, "get_dataset_source_keys",
        lambda dataset_id: {("00123", "AAA", "2014J")} if dataset_id == "dataset-1" else set(),
    )
    updates = []
    monkeypatch.setattr(
        dataset_service, "_update_dataset",
        lambda dataset_id, owner_id, workspace_id, changes: updates.append(
            (dataset_id, owner_id, workspace_id, changes)
        ) or existing,
    )
    processed = []
    monkeypatch.setattr(dataset_service, "_process_parsed_dataset", lambda **kwargs: (
        processed.append(kwargs) or {"data": existing, "validation": {}}
    ))
    monkeypatch.setattr(
        dataset_repository, "create_dataset",
        lambda _payload: pytest.fail("same membership must not create a dataset revision"),
    )

    result = dataset_service.upload_dataset(
        owner_id="owner", workspace_id="workspace", filename="enriched.csv",
        dataset_name="", content=b"enriched source", dataset_id="dataset-1", allow_reprocess=True,
    )

    assert result["data"]["id"] == "dataset-1"
    assert len(processed) == 1
    assert processed[0]["dataset_id"] == "dataset-1"
    assert updates[0][0:3] == ("dataset-1", "owner", "workspace")


def test_failed_dataset_retry_reuses_owned_dataset_id(monkeypatch):
    frame = pd.DataFrame([{"id_student": "1"}])
    existing = {
        "id": "dataset-failed", "status": "failed",
        "validation_results": {"source_fingerprint": dataset_service._source_fingerprint(frame)},
    }
    parsed = SimpleNamespace(frame=frame, report={})
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *_args: existing)
    monkeypatch.setattr(dataset_service, "parse_dataset", lambda *_args: parsed)
    monkeypatch.setattr(dataset_service, "_update_dataset", lambda *_args: existing)
    calls = []
    expected = {"data": {"id": "dataset-failed", "status": "processed"}, "validation": {}}

    def process(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(dataset_service, "_process_parsed_dataset", process)

    result = dataset_service.upload_dataset(
        owner_id="owner", workspace_id="workspace", filename="cohort.csv",
        dataset_name="", content=b"csv", dataset_id="dataset-failed",
    )

    assert result is expected
    assert len(calls) == 1
    assert calls[0]["dataset_id"] == "dataset-failed"
    assert calls[0]["initial_record"] is existing


@pytest.mark.parametrize("status", ["uploaded", "validated", "processing"])
def test_in_progress_dataset_cannot_be_reprocessed(monkeypatch, status):
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *args: {"id": "dataset-1", "status": status})
    with pytest.raises(ValueError):
        dataset_service.upload_dataset(
            owner_id="owner", workspace_id="workspace", filename="cohort.csv",
            dataset_name="", content=b"csv", dataset_id="dataset-1", allow_reprocess=True,
        )
