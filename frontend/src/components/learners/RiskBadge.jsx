const labels = { high: "High risk", medium: "Medium risk", low: "Low risk" };

export default function RiskBadge({ category }) {
  if (!category || !labels[String(category).toLowerCase()]) {
    return <span className="risk-badge" aria-label="Risk category unavailable">Not provided</span>;
  }
  const normalized = String(category).toLowerCase();
  return <span className={`risk-badge risk-${normalized}`}>{labels[normalized]}</span>;
}
