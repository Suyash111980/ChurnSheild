import { useState } from "react";
import { createPredictions } from "../services/predictionService";
export function usePredictions() { const [loading, setLoading] = useState(false); const [error, setError] = useState(null); async function predict(payload) { setLoading(true); setError(null); try { return await createPredictions(payload); } catch (reason) { setError(reason); throw reason; } finally { setLoading(false); } } return { predict, loading, error }; }

