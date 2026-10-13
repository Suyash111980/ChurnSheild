import { Activity, AlertTriangle, ArrowRight, HeartHandshake, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const metricCards = [
  ["Learner records", UsersRound],
  ["Risk distribution", AlertTriangle],
  ["Engagement trends", Activity],
  ["Retention rate", HeartHandshake],
];

export default function Dashboard() {
  const { user } = useAuth();
  const name = user?.name?.split(" ")[0] || "there";

  return <>
    <div className="page-heading dashboard-title">
      <div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {name}</h1><p>Live portfolio insights will appear here when the analytics API is available.</p></div>
      <div className="heading-actions"><Link to="/learners" className="primary-button">Browse learner records <ArrowRight size={15} /></Link></div>
    </div>
    <div className="illustrative-banner api-notice"><span className="banner-spark"><AlertTriangle size={16} /></span><span><strong>Dashboard analytics are unavailable.</strong> The backend does not currently implement a dashboard summary or prediction endpoint. No placeholder statistics are shown as live data.</span></div>
    <section className="metrics-grid unavailable-metrics" aria-label="Dashboard metrics unavailable">
      {metricCards.map(([label, Icon]) => <article className="metric-card unavailable-metric" key={label}>
        <span className="metric-icon violet"><Icon size={19} /></span><p className="metric-label">{label}</p><strong className="unavailable-value">Not available</strong><span className="unavailable-caption">No supporting API response</span>
      </article>)}
    </section>
    <section className="panel dashboard-api-panel">
      <div className="panel-heading"><div><h2>Available learner data</h2><p>The current learner endpoint provides paginated enrollment and demographic records.</p></div><Link className="inline-link" to="/learners">Open learner records <span>→</span></Link></div>
      <div className="dashboard-api-note"><span><UsersRound size={18} /></span><p>Risk categories, prediction scores, engagement history, retention trends, and aggregate totals require backend endpoints that are not yet present in this branch’s backend contract.</p></div>
    </section>
  </>;
}
