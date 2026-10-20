from types import SimpleNamespace

import pytest

from app.services import dataset_service


def test_processed_dataset_can_be_reprocessed_in_place(monkeypatch):
    existing = {"id": "dataset-1", "status": "processed"}
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *args: existing)
    monkeypatch.setattr(dataset_service, "_update_dataset", lambda *args: existing)
    parsed = SimpleNamespace(frame=object(), report={})
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


@pytest.mark.parametrize("status", ["uploaded", "validated", "processing"])
def test_in_progress_dataset_cannot_be_reprocessed(monkeypatch, status):
    monkeypatch.setattr(dataset_service, "get_owned_dataset", lambda *args: {"id": "dataset-1", "status": status})
    with pytest.raises(ValueError):
        dataset_service.upload_dataset(
            owner_id="owner", workspace_id="workspace", filename="cohort.csv",
            dataset_name="", content=b"csv", dataset_id="dataset-1", allow_reprocess=True,
        )
