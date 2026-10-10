export default function RiskBadge({ category = "unknown" }) { return <span className={`risk-badge risk-${category.toLowerCase()}`}>{category}</span>; }
