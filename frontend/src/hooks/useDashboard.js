import { useCallback, useEffect, useRef, useState } from "react";
import { getDashboardSummary } from "../services/dashboardService";

export function useDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const requestId = useRef(0);

  const refresh = useCallback(async ({ initial = false } = {}) => {
    const currentRequest = ++requestId.current;
    if (initial) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const result = await getDashboardSummary();
      if (currentRequest === requestId.current) setData(result);
    } catch (reason) {
      if (currentRequest === requestId.current) setError(reason);
    } finally {
      if (currentRequest === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    refresh({ initial: true });
    return () => { requestId.current += 1; };
  }, [refresh]);

  return { data, loading, refreshing, error, refresh: () => refresh() };
}
