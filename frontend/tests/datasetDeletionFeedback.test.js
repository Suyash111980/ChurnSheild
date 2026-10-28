import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { deleteDatasetAndRefresh, datasetDeletionFeedback } from "../src/services/datasetServiceCore.js";

describe("dataset deletion confirmation feedback", () => {
  it("does not announce success until the DELETE request resolves", async () => {
    let resolveDelete;
    let settled = false;
    const deletion = deleteDatasetAndRefresh({
      dataset: { id: "dataset-1", dataset_name: "Cohort" },
      selectedDatasetId: "dataset-1",
      deleteDataset: () => new Promise((resolve) => { resolveDelete = resolve; }),
      refresh: async () => {},
    }).then((outcome) => { settled = true; return outcome; });
    await Promise.resolve();
    assert.equal(settled, false);
    resolveDelete();
    const outcome = await deletion;
    assert.deepEqual(datasetDeletionFeedback(outcome), {
      message: "Dataset deleted successfully.",
      error: "",
    });
  });
});
