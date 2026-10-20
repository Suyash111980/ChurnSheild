import test from "node:test";
import assert from "node:assert/strict";
import { datasetListState, roleRedirect } from "../src/utils/roleNavigation.js";

test("Master Admin retains workspace access alongside platform pages", () => {
  assert.equal(roleRedirect("master_admin", "/master-admin"), null);
  assert.equal(roleRedirect("master_admin", "/master-admin/oulad"), null);
  assert.equal(roleRedirect("master_admin", "/admin/users"), null);
  assert.equal(roleRedirect("master_admin", "/dashboard"), null);
  assert.equal(roleRedirect("master_admin", "/settings"), null);
});

test("ordinary roles cannot open Master Admin routes directly", () => {
  for (const role of ["admin"]) {
    assert.equal(roleRedirect(role, "/master-admin"), "/dashboard");
    assert.equal(roleRedirect(role, "/master-admin/oulad"), "/dashboard");
  }
});

test("dataset errors are distinct from an actually empty dataset list", () => {
  assert.equal(datasetListState({ loading: true, error: null, datasets: [] }), "loading");
  assert.equal(datasetListState({ loading: false, error: new Error("unavailable"), datasets: [] }), "error");
  assert.equal(datasetListState({ loading: false, error: null, datasets: [] }), "empty");
  assert.equal(datasetListState({ loading: false, error: null, datasets: [{ id: "dataset" }] }), "ready");
});
