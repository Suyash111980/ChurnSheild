import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { confirmAndDeleteDataset, createDatasetService, datasetDeletionFeedback, submitDatasetRevision } from "../src/services/datasetServiceCore.js";

describe("dataset API contract", () => {
  it("uses the registered preview, upload, list, and detail routes", async () => {
    const calls = [];
    const service = createDatasetService(async (...args) => { calls.push(args); return {}; });
    const file = new FormData();
    file.set("file", new Blob(["id_student,code_module,code_presentation\n1,AAA,2014J"]), "cohort.csv");

    await service.previewDataset(file);
    await service.uploadDataset(file);
    await service.listDatasets({ limit: "5", offset: "10" });
    await service.getDataset("dataset/one");
    await service.deleteDataset("dataset/one");

    assert.deepEqual(calls.map(([path]) => path), [
      "/datasets/preview",
      "/datasets/upload",
      "/datasets?limit=5&offset=10",
      "/datasets/dataset%2Fone",
      "/datasets/dataset%2Fone",
    ]);
    assert.equal(calls[0][1].method, "POST");
    assert.equal(calls[0][1].body, file);
    assert.equal(calls[4][1].method, "DELETE");
  });

  it("requires confirmation before deleting and refreshes the selected dataset list", async () => {
    const calls = [];
    const dataset = { id: "d-1", dataset_name: "Spring cohort" };
    const cancelled = await confirmAndDeleteDataset({
      dataset,
      selectedDatasetId: "d-1",
      confirm: (message) => { calls.push(["confirm", message]); return false; },
      deleteDataset: async () => calls.push(["delete"]),
      refresh: async () => calls.push(["refresh"]),
    });
    assert.equal(cancelled.status, "cancelled");
    assert.match(calls[0][1], /permanently removed together/);
    assert.deepEqual(calls.map(([name]) => name), ["confirm"]);

    const confirmedCalls = [];
    const deleted = await confirmAndDeleteDataset({
      dataset,
      selectedDatasetId: "d-1",
      confirm: () => true,
      deleteDataset: async (id) => confirmedCalls.push(["delete", id]),
      refresh: async (preferredId) => confirmedCalls.push(["refresh", preferredId]),
    });
    assert.equal(deleted.status, "deleted");
    assert.deepEqual(confirmedCalls, [["delete", "d-1"], ["refresh", undefined]]);
  });

  it("does not refresh or report deletion when the delete request fails", async () => {
    const calls = [];
    await assert.rejects(confirmAndDeleteDataset({
      dataset: { id: "d-2", dataset_name: "Winter cohort" },
      selectedDatasetId: "d-2",
      confirm: () => true,
      deleteDataset: async () => { calls.push("delete"); throw new Error("RLS denied"); },
      refresh: async () => calls.push("refresh"),
    }), /RLS denied/);
    assert.deepEqual(calls, ["delete"]);
  });

  it("shows the exact success notification only after deletion, including refresh failure", async () => {
    const outcomes = [];
    const normal = await confirmAndDeleteDataset({
      dataset: { id: "d-4", dataset_name: "Cohort" },
      selectedDatasetId: "d-4",
      confirm: () => true,
      deleteDataset: async () => { outcomes.push("delete succeeded"); },
      refresh: async () => { outcomes.push("refresh succeeded"); },
    });
    assert.deepEqual(outcomes, ["delete succeeded", "refresh succeeded"]);
    assert.deepEqual(datasetDeletionFeedback(normal), {
      message: "Dataset deleted successfully.",
      error: "",
    });

    const refreshedFailure = datasetDeletionFeedback({
      status: "deleted_refresh_failed",
      error: new Error("workspace list unavailable"),
    });
    assert.deepEqual(refreshedFailure, {
      message: "Dataset deleted successfully.",
      error: "The dataset was deleted, but the list could not refresh: workspace list unavailable",
    });
    assert.equal(datasetDeletionFeedback({ status: "cancelled" }), null);
  });

  it("distinguishes a successful deletion from a failed list refresh", async () => {
    const result = await confirmAndDeleteDataset({
      dataset: { id: "d-3", dataset_name: "Autumn cohort" },
      selectedDatasetId: "d-other",
      confirm: () => true,
      deleteDataset: async () => {},
      refresh: async (preferredId) => {
        assert.equal(preferredId, "d-other");
        throw new Error("list unavailable");
      },
    });
    assert.equal(result.status, "deleted_refresh_failed");
    assert.match(result.error.message, /list unavailable/);
  });

  it("uses only registered retry and reprocess actions and propagates failures", async () => {
    const calls = [];
    const service = createDatasetService(async (...args) => {
      calls.push(args);
      if (args[0].includes("retry")) throw new Error("retry rejected");
      return {};
    });
    const file = new FormData();
    await assert.rejects(service.retryDataset("d-1", file), /retry rejected/);
    await service.reprocessDataset("d-2", file);

    assert.deepEqual(calls.map(([path]) => path), [
      "/datasets/d-1/retry",
      "/datasets/d-2/reprocess",
    ]);
    assert.equal(calls[0][1].method, "POST");
    assert.equal(calls[0][1].body, file);
  });

  it("refreshes the returned dataset after retry or reprocess succeeds", async () => {
    const calls = [];
    const file = new File(["id_student,code_module,code_presentation\n1,AAA,2014J"], "cohort.csv");
    const response = { data: { id: "dataset-returned", status: "processed" } };
    const result = await submitDatasetRevision({
      datasetId: "dataset-requested",
      status: "processed",
      file,
      retryDataset: async (...args) => { calls.push(["retry", ...args]); return response; },
      reprocessDataset: async (...args) => { calls.push(["reprocess", ...args]); return response; },
      refresh: async (id) => calls.push(["refresh", id]),
    });

    assert.equal(result, response);
    assert.equal(calls[0][0], "reprocess");
    assert.equal(calls[0][1], "dataset-requested");
    assert.equal(calls[0][2].get("file"), file);
    assert.deepEqual(calls[1], ["refresh", "dataset-returned"]);
  });

  it("uses the retry route for failed datasets and does not refresh on failure", async () => {
    const calls = [];
    await assert.rejects(submitDatasetRevision({
      datasetId: "dataset-failed",
      status: "failed",
      file: new File([""], "cohort.csv"),
      retryDataset: async () => { calls.push("retry"); throw new Error("retry failed"); },
      reprocessDataset: async () => { calls.push("reprocess"); return {}; },
      refresh: async () => calls.push("refresh"),
    }), /retry failed/);
    assert.deepEqual(calls, ["retry"]);
  });

  it("keeps the completed upload result visible when refreshing the list fails", async () => {
    const response = { data: { id: "dataset-saved", status: "processed" } };
    const observed = [];
    await submitDatasetRevision({
      datasetId: "dataset-old",
      status: "failed",
      file: new File(["csv"], "cohort.csv"),
      retryDataset: async () => response,
      reprocessDataset: async () => ({}),
      refresh: async () => { throw new Error("list unavailable"); },
      onResponse: (value) => observed.push(["response", value]),
      onRefreshError: (error) => observed.push(["refresh-error", error.message]),
    });
    assert.deepEqual(observed, [
      ["response", response],
      ["refresh-error", "list unavailable"],
    ]);
  });
});
