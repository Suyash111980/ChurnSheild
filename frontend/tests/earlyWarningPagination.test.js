import test from "node:test";
import assert from "node:assert/strict";
import {
  EARLY_WARNING_PAGE_SIZE,
  earlyWarningSummary,
  nextEarlyWarningOffset,
  previousEarlyWarningOffset,
} from "../src/utils/earlyWarningPagination.js";

test("Early Warning pagination exposes every eligible row across stable API pages", () => {
  const total = 750;
  const seen = new Set();
  const offsets = [];
  let offset = 0;
  let hasMore = true;
  while (hasMore) {
    offsets.push(offset);
    const count = Math.min(EARLY_WARNING_PAGE_SIZE, total - offset);
    for (let index = offset; index < offset + count; index += 1) {
      const recordId = `learner-course-${index}`;
      assert.equal(seen.has(recordId), false, `duplicate record ${recordId}`);
      seen.add(recordId);
    }
    hasMore = offset + count < total;
    offset = nextEarlyWarningOffset(offset, { limit: EARLY_WARNING_PAGE_SIZE, has_more: hasMore });
  }
  assert.deepEqual(offsets, [0, 100, 200, 300, 400, 500, 600, 700]);
  assert.equal(seen.size, total);
  assert.equal(previousEarlyWarningOffset(offset, { limit: EARLY_WARNING_PAGE_SIZE }), 600);
});

test("Early Warning summary reports saved predictions and persisted distribution separately", () => {
  assert.deepEqual(earlyWarningSummary({
    total_learner_records: 750,
    learners_with_prediction: 620,
    prediction_coverage: 620 / 750,
    risk_distribution: { high: 90, medium: 210, low: 320 },
  }), {
    learnerRecords: 750,
    savedPredictions: 620,
    coverage: 620 / 750,
    high: 90,
    medium: 210,
    low: 320,
  });
  assert.deepEqual(earlyWarningSummary({
    total_learner_records: 750,
    learners_with_prediction: 0,
    prediction_coverage: 0,
    risk_distribution: null,
  }), {
    learnerRecords: 750,
    savedPredictions: 0,
    coverage: 0,
    high: null,
    medium: null,
    low: null,
  });
});

test("Early Warning pagination stops at the server-reported end", () => {
  assert.equal(nextEarlyWarningOffset(700, { limit: 100, has_more: false }), 700);
});
