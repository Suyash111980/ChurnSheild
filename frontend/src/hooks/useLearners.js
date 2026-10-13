import { useCallback, useEffect, useState } from "react";
import { getLearners } from "../services/learnerService";

export function useLearners({ limit = 20, offset = 0 } = {}) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getLearners({ limit, offset }, { signal: controller.signal })
      .then((result) => {
        if (!Array.isArray(result?.data)) {
          throw new Error("The learner service returned an unexpected response.");
        }
        setData(result.data);
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [limit, offset, requestVersion]);

  const retry = useCallback(() => setRequestVersion((version) => version + 1), []);
  return { data, loading, error, retry };
}
