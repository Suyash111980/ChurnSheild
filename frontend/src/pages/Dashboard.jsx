import { Activity, ArrowRight, Database, Download, ShieldAlert, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useDataset } from "../context/DatasetContext";
import { useDashboard } from "../hooks/useDashboard";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import { datasetListState } from "../utils/roleNavigation";
import { getAvatarDetails } from "../utils/userAvatar";

function Metric({ label, value, note, Icon, tone = "violet" }) {
  return <article className="metric-card"><div className="metric-top"><span className={`metric-icon ${tone}`}><Icon size={18} /></span></div><p className="metric-label">{label}</p><strong className="metric-value">{value}</strong><div className="metric-footer">{note}</div></article>;
}

function RiskPanel({ data }) {
  const distribution = data?.risk_distribution;
  const total = distribution ? Object.values(distribution).reduce((sum, value) => sum + value, 0) : 0;
  const percentages = total ? [distribution.low, distribution.medium, distribution.high].map((value) => value / total * 100) : [0, 0, 0];
  const endLow = percentages[0];
  const endMedium = endLow + percentages[1];
  return <article className="panel risk-panel">
    <div className="panel-heading"><div><h2>Persisted risk distribution</h2><p>Latest saved predictions in this dataset</p></div><Link className="inline-link" to="/early-warning">Open early warning <span>→</span></Link></div>
    {distribution && total > 0 ? <div className="risk-breakdown"><div className="donut-wrap"><div className="donut" style={{ background: `conic-gradient(#12b6a3 0 ${endLow}%, #6948f5 ${endLow}% ${endMedium}%, #e7465b ${endMedium}% 100%)` }}><div className="donut-center"><strong>{total.toLocaleString()}</strong><span>predictions</span></div></div></div><div className="risk-legend"><div><span><i className="risk-low"/>Low</span><strong>{distribution.low}</strong></div><div><span><i className="risk-medium"/>Medium</span><strong>{distribution.medium}</strong></div><div><span><i className="risk-high"/>High</span><strong>{distribution.high}</strong></div></div></div> : <div className="dashboard-api-note"><span><ShieldAlert size={18} /></span><p>No persisted predictions are available for this dataset. Learners without saved predictions are not assigned a risk category.</p></div>}
  </article>;
}

export default function Dashboard() {
  const { user, accountProfile } = useAuth();
  const { dataset, datasets, datasetId, selectDataset, loading: datasetsLoading, error: datasetsError, refresh } = useDataset();
  const { data, loading, error, retry } = useDashboard();
  const listState = datasetListState({ loading: datasetsLoading, error: datasetsError, datasets });
  const displayLabel = getAvatarDetails(user, accountProfile).label;
  const firstName = displayLabel === "User" ? "there" : displayLabel.split(" ")[0];

  if (listState === "loading") return <><div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>Loading your workspace datasets…</p></div></div><LoadingState rows={3} label="Loading datasets" /></>;
  if (listState === "error") return <><div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>Workspace information is temporarily unavailable.</p></div></div><ErrorState title="Workspace data unavailable" message="We couldn’t retrieve this workspace’s dataset list. Retry, or contact support if the problem continues." onRetry={() => refresh().catch(() => {})} /></>;

  if (listState === "empty") return <>
    <div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>Your workspace is ready for a dataset.</p></div>{["admin", "master_admin"].includes(accountProfile?.app_role) && <div className="heading-actions"><Link to="/datasets" className="primary-button">Add dataset <ArrowRight size={15} /></Link></div>}</div>
    <section className="panel dashboard-api-panel"><div className="panel-heading"><div><h2>No datasets yet</h2><p>Add a dataset to begin exploring learner records and saved results.</p></div><span className="metric-icon violet"><Database size={18} /></span></div>{["admin", "master_admin"].includes(accountProfile?.app_role) && <Link to="/datasets" className="primary-button">Add dataset <ArrowRight size={15} /></Link>}</section>
  </>;

  return <>
    <div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>{dataset?.dataset_name || "Selected dataset"} · Summary of persisted learner records and predictions.</p></div><div className="heading-actions">
      {datasets.length > 1 && <label className="dashboard-dataset-select"><span className="sr-only">Active dataset</span><select aria-label="Active dataset" value={datasetId} onChange={(event) => selectDataset(event.target.value)}>{datasets.map((item) => <option key={item.id} value={item.id}>{item.dataset_name} · {item.status}</option>)}</select></label>}
      {accountProfile?.app_role === "admin" && <Link to="/reports" className="secondary-button"><Download size={15}/> Export overview</Link>}
      <Link to="/early-warning" className="primary-button"><ShieldAlert size={15}/> Review high-risk</Link>
    </div></div>
    {dataset?.status === "failed" && <ErrorState title="Dataset processing failed" message={dataset.error_summary || "Review the dataset validation results and retry processing."} onRetry={() => refresh().catch(() => {})} />}
    {dataset && dataset.status !== "processed" && dataset.status !== "failed" && <div className="illustrative-banner api-notice"><span className="banner-spark"><Activity size={16} /></span><span><strong>Processing in progress.</strong> Dashboard statistics will appear when this dataset is ready.</span></div>}
    {dataset?.status === "processed" && <>
      {loading && <LoadingState rows={2} label="Loading dataset summary" />}
      {error && <ErrorState title="Dashboard unavailable" message="The saved summary could not be loaded. Your dataset remains selected." onRetry={retry} />}
      {!loading && !error && data && <>
        <section className="metrics-grid" aria-label="Dataset summary">
          <Metric Icon={UsersRound} label="Learner-course records" value={data.total_learner_records.toLocaleString()} note="Records in selected dataset" />
          <Metric Icon={ShieldAlert} tone="red" label="High-risk records" value={data.risk_distribution ? data.risk_distribution.high.toLocaleString() : "Unavailable"} note="Persisted predictions only" />
          <Metric Icon={Activity} tone="amber" label="Medium-risk records" value={data.risk_distribution ? data.risk_distribution.medium.toLocaleString() : "Unavailable"} note="Persisted predictions only" />
          <Metric Icon={Database} tone="green" label="Historical outcomes" value="Unavailable" note="Not included in the dashboard API" />
        </section>
        <section className="dashboard-grid"><RiskPanel data={data} /><article className="panel engagement-panel"><div className="panel-heading"><div><h2>Historical outcomes</h2><p>Historical outcome breakdown is not available from the current dataset API.</p></div><span className="metric-icon blue"><Activity size={18} /></span></div><div className="dashboard-api-note"><span><UsersRound size={18} /></span><p>Historical OULAD outcomes and operational predictions are separate. No outcome chart is shown without persisted outcome data.</p></div><Link className="inline-link" to="/learners">Browse learner records <span>→</span></Link></article></section>
      </>}
    </>}
  </>;
}
