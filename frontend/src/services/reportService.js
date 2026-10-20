import { apiFetch } from "./apiClient";

export async function downloadLearnerCsv(datasetId) {
  if (!datasetId) throw new Error("Select a dataset before exporting learner records.");
  const response = await apiFetch(`/reports/learners.csv?dataset_id=${encodeURIComponent(datasetId)}`);
  if (!response.ok) throw new Error(`Learner export failed (${response.status}).`);

  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "churnshield-learners.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
