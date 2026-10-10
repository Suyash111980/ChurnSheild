import { useEffect, useState } from "react";
import { getLearners } from "../services/learnerService";
export function useLearners(params = {}) { const [data, setData] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(null); useEffect(() => { let active = true; getLearners(params).then((result) => { if (active) setData(result.data || []); }).catch((reason) => { if (active) setError(reason); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [JSON.stringify(params)]); return { data, loading, error }; }

