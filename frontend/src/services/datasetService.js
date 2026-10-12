import { apiRequest } from "./apiClient";

export const uploadDataset = (formData) =>
  apiRequest("/datasets/upload", { method: "POST", body: formData });
