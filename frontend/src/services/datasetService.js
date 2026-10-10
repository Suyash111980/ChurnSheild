import { apiRequest } from "./apiClient";
export const uploadDataset = (formData) => fetch(`${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"}/datasets/upload`, { method: "POST", body: formData }).then((response) => { if (!response.ok) throw new Error("Dataset upload failed"); return response.json(); });
