import { useCallback, useEffect, useState } from "react";
import { listPredictions } from "../services/predictionService";

export function usePredictions({ datasetId, limit = 20, offset = 0, risk_category, code_module, code_presentation } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    if (!datasetId) { setLoading(false); return () => { active = false; }; }
    setLoading(true);
    listPredictions({ dataset_id: datasetId, limit, offset, risk_category, code_module, code_presentation })
      .then((result) => { if (active) setData(result); })
      .catch((reason) => { if (active) setError(reason); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [datasetId, limit, offset, risk_category, code_module, code_presentation, requestVersion]);

  const retry = useCallback(() => setRequestVersion((version) => version + 1), []);
  return { data, loading, error, retry };
}

