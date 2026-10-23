import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { datasetScopeParams, datasetScopeQuery } from "../src/utils/datasetScope.js";

describe("dataset scope API contract", () => {
  it("serializes overall scope separately from the UUID dataset parameter", () => {
    const params = datasetScopeParams("all", { limit: 20, offset: 0 });
    assert.deepEqual(params, { limit: 20, offset: 0, scope: "all" });
    assert.equal("dataset_id" in params, false);
    assert.equal(datasetScopeQuery("all", { limit: 20 }), "limit=20&scope=all");
  });

  it("preserves individual dataset UUID selection and filters", () => {
    const id = "0baf212f-6202-44fe-abf7-7813c45b6d66";
    assert.deepEqual(datasetScopeParams(id, { risk_category: "high" }), { risk_category: "high", dataset_id: id });
    assert.equal(datasetScopeQuery(id), `dataset_id=${id}`);
  });

  it("accepts an explicit overall scope without a dataset id", () => {
    assert.deepEqual(datasetScopeParams(undefined, { scope: "all", limit: 20 }), { limit: 20, scope: "all" });
  });
});
