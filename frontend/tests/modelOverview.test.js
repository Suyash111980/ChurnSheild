import test from "node:test";
import assert from "node:assert/strict";
import { confusionMatrixRows, formatModelMetric, hyperparameterEntries, modelStatusLabel, overviewState } from "../src/utils/modelOverview.js";

test("formats actual evaluation values without changing raw values", () => {
  const evaluation = { precision: 0.8, recall: 0.5654, f1: 0.6625, roc_auc: 0.8195, pr_auc_average_precision: 0.7596, record_count: 1363, decision_threshold: 0.5 };
  assert.equal(formatModelMetric("precision", evaluation.precision), "80.0%");
  assert.equal(formatModelMetric("recall", evaluation.recall), "56.5%");
  assert.equal(formatModelMetric("f1", evaluation.f1), "66.3%");
  assert.equal(formatModelMetric("roc_auc", evaluation.roc_auc), "82.0%");
  assert.equal(formatModelMetric("pr_auc_average_precision", evaluation.pr_auc_average_precision), "76.0%");
  assert.equal(formatModelMetric("record_count", evaluation.record_count), "1363");
  assert.equal(formatModelMetric("decision_threshold", evaluation.decision_threshold), "50.0%");
  assert.equal(evaluation.precision, 0.8);
});

test("keeps unavailable values and inference states distinct", () => {
  assert.equal(formatModelMetric("precision", null), "Not available");
  assert.equal(modelStatusLabel("loaded"), "Loaded successfully");
  assert.equal(modelStatusLabel("sample_scored"), "Sample scored");
  assert.equal(modelStatusLabel("not_generated"), "Not generated");
  assert.equal(modelStatusLabel("not_implemented"), "Not implemented");
});

test("API failures remain an error state with a retryable UI branch", () => {
  assert.equal(overviewState({ loading: false, error: "OULAD overview is unavailable.", result: null }), "error");
  assert.equal(overviewState({ loading: false, error: "", result: null }), "unavailable");
  assert.equal(overviewState({ loading: true, error: "", result: null }), "loading");
});

test("renders only a valid structured confusion matrix and metadata", () => {
  assert.deepEqual(confusionMatrixRows({ labels: [0, 1], rows_actual_columns_predicted: [[822, 67], [206, 268]] }), [
    { actual: 0, values: [822, 67] },
    { actual: 1, values: [206, 268] },
  ]);
  assert.equal(confusionMatrixRows({ labels: [0, 1], rows_actual_columns_predicted: [[1], [2]] }), null);
  assert.deepEqual(hyperparameterEntries({ n_estimators: 300 }), [["n_estimators", 300]]);
  assert.deepEqual(hyperparameterEntries(null), []);
});
