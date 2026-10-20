import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "../services/apiClient";
import { useAuth } from "./AuthContext";

const Context = createContext(null);
const STORAGE_KEY = "churnshield.dataset";

export function DatasetProvider({ children }) {
  const { user } = useAuth();
  const [result, setResult] = useState({ userId: null, datasets: [], loading: true, error: null });
  const [selectedId, setSelectedId] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    if (!user) {
      setResult({ userId: null, datasets: [], loading: false, error: null });
      setSelectedId("");
      localStorage.removeItem(STORAGE_KEY);
      return () => {};
    }

    setResult({ userId: user.id, datasets: [], loading: true, error: null });
    setSelectedId("");
    apiRequest("/datasets?limit=100&offset=0").then((response) => {
      if (version !== requestVersion.current) return;
      const rows = Array.isArray(response.data) ? response.data : [];
      const saved = localStorage.getItem(STORAGE_KEY);
      const chosen = rows.find((row) => row.id === saved) || rows.find((row) => row.status === "processed") || rows[0];
      setResult({ userId: user.id, datasets: rows, loading: false, error: null });
      setSelectedId(chosen?.id || "");
      if (chosen?.id) localStorage.setItem(STORAGE_KEY, chosen.id);
      else localStorage.removeItem(STORAGE_KEY);
    }).catch((error) => {
      if (version !== requestVersion.current) return;
      setResult({ userId: user.id, datasets: [], loading: false, error });
      setSelectedId("");
      localStorage.removeItem(STORAGE_KEY);
    });
    return () => { if (version === requestVersion.current) requestVersion.current += 1; };
  }, [user?.id]);

  const selectDataset = useCallback((id) => {
    setSelectedId(id || "");
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  }, []);

  const datasetsAreCurrent = Boolean(user?.id) && result.userId === user.id;
  const currentDatasets = datasetsAreCurrent ? result.datasets : [];
  const currentDatasetId = datasetsAreCurrent && currentDatasets.some((row) => row.id === selectedId) ? selectedId : "";

  const refresh = useCallback(async (preferredId) => {
    if (!user?.id) return [];
    const version = ++requestVersion.current;
    setResult((current) => ({
      userId: user.id,
      datasets: current.userId === user.id ? current.datasets : [],
      loading: true,
      error: null,
    }));
    try {
      const response = await apiRequest("/datasets?limit=100&offset=0");
      const rows = Array.isArray(response.data) ? response.data : [];
      if (version !== requestVersion.current) return rows;
      const preferred = preferredId || selectedId;
      const chosen = rows.find((row) => row.id === preferred) || rows.find((row) => row.status === "processed") || rows[0];
      setResult({ userId: user.id, datasets: rows, loading: false, error: null });
      setSelectedId(chosen?.id || "");
      if (chosen?.id) localStorage.setItem(STORAGE_KEY, chosen.id);
      else localStorage.removeItem(STORAGE_KEY);
      return rows;
    } catch (error) {
      if (version === requestVersion.current) {
        setResult({ userId: user.id, datasets: [], loading: false, error });
        setSelectedId("");
        localStorage.removeItem(STORAGE_KEY);
      }
      throw error;
    }
  }, [user?.id, selectedId]);

  const value = useMemo(() => ({
    datasets: currentDatasets,
    datasetId: currentDatasetId,
    dataset: currentDatasets.find((item) => item.id === currentDatasetId) || null,
    selectDataset,
    refresh,
    loading: Boolean(user?.id) && (!datasetsAreCurrent || result.loading),
    error: datasetsAreCurrent ? result.error : null,
  }), [currentDatasets, currentDatasetId, selectDataset, refresh, user?.id, datasetsAreCurrent, result.loading, result.error]);

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export const useDataset = () => {
  const value = useContext(Context);
  if (!value) throw new Error("useDataset must be used inside DatasetProvider");
  return value;
};
