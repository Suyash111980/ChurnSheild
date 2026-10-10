export function downloadReport(format = "xlsx") {
  const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
  window.location.assign(`${base}/reports/export?format=${encodeURIComponent(format)}`);
}
