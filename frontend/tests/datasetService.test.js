import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createDatasetService, submitDatasetRevision } from "../src/services/datasetServiceCore.js";

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

    assert.deepEqual(calls.map(([path]) => path), [
      "/datasets/preview",
      "/datasets/upload",
      "/datasets?limit=5&offset=10",
      "/datasets/dataset%2Fone",
    ]);
    assert.equal(calls[0][1].method, "POST");
    assert.equal(calls[0][1].body, file);
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
