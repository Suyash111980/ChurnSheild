import { useEffect, useState } from "react";
import { getDashboardSummary } from "../services/dashboardService";
export function useDashboard() { const [data, setData] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(null); useEffect(() => { let active = true; getDashboardSummary().then((result) => { if (active) setData(result); }).catch((reason) => { if (active) setError(reason); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []); return { data, loading, error }; }

