import { useCallback, useEffect, useState } from "react";
import { getLearners } from "../services/learnerService";
import { useDataset } from "../context/DatasetContext";

export function useLearners({ limit = 20, offset = 0 } = {}) {
  const { datasetId } = useDataset();
  const [page, setPage] = useState({ datasetId: null, data: [], total: 0, loading: true, error: null });
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setPage({ datasetId, data: [], total: 0, loading: Boolean(datasetId), error: null });

    if (!datasetId) return () => controller.abort();
    getLearners({ dataset_id: datasetId, limit, offset }, { signal: controller.signal })
      .then((result) => {
        if (!Array.isArray(result?.data)) {
          throw new Error("The learner service returned an unexpected response.");
        }
        setPage({ datasetId, data: result.data, total: Number(result.total) || 0, loading: false, error: null });
      })
      .catch((error) => {
        if (error.name !== "AbortError") setPage({ datasetId, data: [], total: 0, loading: false, error });
      });

    return () => controller.abort();
  }, [datasetId, limit, offset, requestVersion]);

  const retry = useCallback(() => setRequestVersion((version) => version + 1), []);
  const current = page.datasetId === datasetId;
  return {
    data: current ? page.data : [],
    total: current ? page.total : 0,
    loading: Boolean(datasetId) && (!current || page.loading),
    error: current ? page.error : null,
    retry,
  };
}
