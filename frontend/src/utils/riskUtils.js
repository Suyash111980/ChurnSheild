export const RISK_CATEGORIES = ["low", "medium", "high"];
export function riskCategory(probability) {
  const score = Number(probability);
  if (!Number.isFinite(score)) return "unknown";
  if (score >= 0.7) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}
