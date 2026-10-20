import { Activity, AlertTriangle, ArrowRight, HeartHandshake, RefreshCw, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import KpiCard from "../components/dashboard/KpiCard";
import DashboardCharts from "../components/dashboard/DashboardCharts";
import { useDashboard } from "../hooks/useDashboard";
import { useLearners } from "../hooks/useLearners";

const metricCards = [
  { keys: ["total_learners", "totalLearners"], label: "Total learner records", icon: UsersRound, tone: "blue", to: "/learners", description: "Open learner directory" },
  { keys: ["high_risk_learners", "highRiskLearners"], label: "High-risk learners", icon: AlertTriangle, tone: "amber", to: "/early-warning?risk=high", description: "Review high-risk warnings" },
  { keys: ["declining_engagement", "decliningEngagement"], label: "Declining engagement", icon: Activity, tone: "violet", to: "/early-warning?q=declining", description: "Review engagement warnings" },
  { keys: ["retention_rate", "retentionRate"], label: "Retention rate", icon: HeartHandshake, tone: "green", unit: "%", description: "Portfolio retention" },
];

function getMetricValue(summary, keys, unit) {
  // These fields are the dashboard summary contract. Unknown and missing values stay unavailable.
  for (const key of keys) {
    const value = summary?.[key];
    if (value === null || value === undefined || value === "") continue;
    const numericValue = typeof value === "number" ? value : Number(String(value).replaceAll(",", "").replace(/%$/, ""));
    if (Number.isFinite(numericValue)) return unit === "%" && numericValue >= 0 && numericValue <= 1 ? numericValue * 100 : numericValue;
  }
  return null;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, loading, refreshing, error, refresh } = useDashboard();
  const learnerPage = useLearners({ limit: 20, offset: 0 });
  const name = user?.name?.split(" ")[0] || "there";
  const summary = data?.data ?? data?.summary ?? data;
  const hasMetric = metricCards.some(({ keys, unit }) => getMetricValue(summary, keys, unit) !== null);

  return <>
    <div className="page-heading dashboard-title">
      <div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {name}</h1><p>Your learner retention overview and the signals that need attention.</p></div>
      <div className="heading-actions"><button type="button" className="secondary-button kpi-refresh-button" onClick={() => refresh()} disabled={refreshing} aria-label="Refresh dashboard metrics"> <RefreshCw size={14} className={refreshing ? "kpi-refreshing" : ""} /> Refresh</button><Link to="/learners" className="primary-button">Browse learner records <ArrowRight size={15} /></Link></div>
    </div>
    {!loading && (error || !hasMetric) && <div className="illustrative-banner api-notice" role="status"><span className="banner-spark"><AlertTriangle size={16} /></span><span><strong>Dashboard metrics {error ? "could not be loaded" : "are not available yet"}.</strong> The summary endpoint may not be available in this backend. Metrics without a response are shown as “Not available”; no values are invented.</span></div>}
    <section className="metrics-grid unavailable-metrics dashboard-kpis" aria-label="Dashboard key performance indicators" aria-busy={loading || refreshing}>
      {metricCards.map(({ keys, label, icon: Icon, tone, to, unit, description }, index) => <KpiCard
        key={label}
        label={label}
        value={getMetricValue(summary, keys, unit)}
        loading={loading}
        icon={Icon}
        tone={tone}
        unit={unit}
        to={to}
        description={description}
        index={index}
      />)}
    </section>
    <DashboardCharts learners={learnerPage.data} loading={learnerPage.loading} error={learnerPage.error} retry={learnerPage.retry}/>
    <section className="panel dashboard-api-panel">
      <div className="panel-heading"><div><h2>Available learner data</h2><p>The current learner endpoint provides paginated enrollment and demographic records.</p></div><Link className="inline-link" to="/learners">Open learner records <span>→</span></Link></div>
      <div className="dashboard-api-note"><span><UsersRound size={18} /></span><p>Risk categories, prediction scores, engagement history, retention trends, and aggregate totals require backend summary and prediction fields. KPIs use only fields returned by the existing summary service and never substitute demo numbers.</p></div>
    </section>
  </>;
}
