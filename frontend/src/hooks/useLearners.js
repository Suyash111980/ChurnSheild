import { useCallback, useEffect, useState } from "react";
import { getLearners } from "../services/learnerService";
import { useDataset } from "../context/DatasetContext";
import { datasetScopeParams } from "../utils/datasetScope";

export function useLearners({ limit = 20, offset = 0, datasetId: requestedDatasetId, ...filters } = {}) {
  const { datasetId: activeDatasetId } = useDataset();
  const datasetId = requestedDatasetId === undefined ? activeDatasetId : requestedDatasetId;
  const [page, setPage] = useState({ datasetId: null, data: [], total: 0, loading: true, error: null });
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setPage({ datasetId, data: [], total: 0, loading: Boolean(datasetId), error: null });

    if (!datasetId) return () => controller.abort();
    getLearners({
      ...datasetScopeParams(datasetId),
      limit,
      offset,
      q: filters.q,
      code_module: filters.module,
      code_presentation: filters.presentation,
      risk_category: filters.risk_category,
      sort: filters.sort,
      direction: filters.direction,
    }, { signal: controller.signal })
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
  }, [datasetId, limit, offset, requestVersion, filters.q, filters.module, filters.presentation, filters.risk_category, filters.sort, filters.direction]);

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
