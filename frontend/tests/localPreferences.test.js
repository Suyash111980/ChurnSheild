import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readLocalPreference, writeLocalPreference } from "../src/utils/localPreferences.js";

function storageMock() {
  const values = new Map();
  return {
    getItem: (key) => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, value),
  };
}

describe("browser-local preferences", () => {
  it("persists and restores a value without implying server synchronization", () => {
    const storage = storageMock();
    assert.equal(readLocalPreference("alerts", true, storage), true);
    assert.equal(writeLocalPreference("alerts", false, storage), true);
    assert.equal(readLocalPreference("alerts", true, storage), false);
  });

  it("uses a safe fallback when browser storage is unavailable", () => {
    const unavailable = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
    assert.equal(readLocalPreference("alerts", true, unavailable), true);
    assert.equal(writeLocalPreference("alerts", false, unavailable), false);
  });
});
