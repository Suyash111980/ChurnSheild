import { apiFetch } from "./apiClient";

export async function downloadReport(format = "xlsx") {
  const response = await apiFetch(
    `/reports/export?format=${encodeURIComponent(format)}`,
  );
  if (!response.ok) throw new Error(`Report request failed (${response.status})`);

  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `churnshield-report.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
