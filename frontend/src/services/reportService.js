import { apiFetch } from "./apiClient";

async function downloadCsv(datasetId, path, filename, title) {
  if (!datasetId) throw new Error("Select a dataset before exporting.");
  const response = await apiFetch(`${path}?dataset_id=${encodeURIComponent(datasetId)}`);
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json())?.detail || ""; } catch { /* Response may not contain JSON. */ }
    throw new Error(detail || `${title} export failed (${response.status}).`);
  }

  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const downloadLearnerCsv = (datasetId) => downloadCsv(
  datasetId, "/reports/learners.csv", "churnshield-learners.csv", "Learner",
);
export const downloadRiskAnalysisCsv = (datasetId) => downloadCsv(
  datasetId, "/reports/risk-analysis.csv", "churnshield-risk-analysis.csv", "Risk Analysis",
);
export const downloadRecommendationsCsv = (datasetId) => downloadCsv(
  datasetId, "/reports/recommendations.csv", "churnshield-recommendations.csv", "Recommendation",
);
