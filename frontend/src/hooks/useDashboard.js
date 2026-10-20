import { useCallback, useEffect, useState } from "react";
import { useDataset } from "../context/DatasetContext";
import { getDashboardSummary } from "../services/dashboardService";

export function useDashboard() {
  const { datasetId } = useDataset();
  const [result, setResult] = useState({ datasetId: null, data: null, error: null, loading: true });
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    if (!datasetId) {
      setResult({ datasetId: null, data: null, error: null, loading: false });
      return () => { active = false; };
    }

    setResult({ datasetId, data: null, error: null, loading: true });
    getDashboardSummary(datasetId)
      .then((data) => { if (active) setResult({ datasetId, data, error: null, loading: false }); })
      .catch((error) => { if (active) setResult({ datasetId, data: null, error, loading: false }); });
    return () => { active = false; };
  }, [datasetId, requestVersion]);

  const retry = useCallback(() => setRequestVersion((version) => version + 1), []);
  const current = result.datasetId === datasetId;
  const loading = Boolean(datasetId) && (!current || result.loading);

  return {
    data: current ? result.data : null,
    error: current ? result.error : null,
    loading,
    refreshing: false,
    retry,
    refresh: retry,
  };
}
