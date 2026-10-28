import { Activity, ArrowRight, Database, Download, ShieldAlert, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useDataset } from "../context/DatasetContext";
import { useDashboard } from "../hooks/useDashboard";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import RiskDistributionChart from "../components/dashboard/RiskDistributionChart";
import { datasetListState } from "../utils/roleNavigation";
import { getAvatarDetails } from "../utils/userAvatar";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";
import DatasetScopeSelect from "../components/common/DatasetScopeSelect";
import "./Dashboard.css";

function Metric({ label, value, note, Icon, tone = "violet", to }) {
  const className = `metric-card metric-card-tone-${tone}${to ? " metric-card-link" : ""}`;
  const contents = <><div className="metric-top"><span className={`metric-icon ${tone}`}><Icon size={18} /></span></div><p className="metric-label">{label}</p><strong className="metric-value">{value}</strong><div className="metric-footer">{note}</div></>;
  return to ? <Link className={className} to={to} aria-label={`${label}: ${value}. ${note}`}>{contents}</Link> : <article className={className}>{contents}</article>;
}

function RiskAnalysisMetric({ data, destination }) {
  const distribution = data?.risk_distribution;
  const predictionCount = Number(data?.learners_with_prediction) || 0;
  const hasRiskCounts = predictionCount > 0 && distribution;
  return <Link className="metric-card metric-card-link risk-analysis-metric metric-card-tone-red" to={destination} aria-label={`Risk Analysis: ${predictionCount.toLocaleString()} learners with saved predictions. Open Early Warning Center.`}>
    <div className="metric-top"><span className="metric-icon red"><ShieldAlert size={18}/></span></div>
    <p className="metric-label">Risk Analysis</p>
    <strong className="metric-value">{predictionCount.toLocaleString()} learners</strong>
    <span className="risk-analysis-caption">with saved predictions</span>
    {hasRiskCounts ? <div className="risk-analysis-counts" aria-label="Saved predictions by risk category"><div className="risk-count-item high"><span className="risk-count-label"><i/>High</span><strong>{distribution.high.toLocaleString()}</strong></div><div className="risk-count-item medium"><span className="risk-count-label"><i/>Medium</span><strong>{distribution.medium.toLocaleString()}</strong></div><div className="risk-count-item low"><span className="risk-count-label"><i/>Low</span><strong>{distribution.low.toLocaleString()}</strong></div></div> : <span className="risk-analysis-caption">Risk distribution unavailable; records without predictions are unranked.</span>}
  </Link>;
}

export default function Dashboard() {
  const { user, accountProfile } = useAuth();
  const { dataset, datasets, datasetId, selectDataset, loading: datasetsLoading, error: datasetsError, refresh } = useDataset();
  const [overallScope, setOverallScope] = useState(false);
  const [pendingScope, setPendingScope] = useState(null);
  const activeDatasetId = overallScope ? "all" : datasetId;
  const { data, loading, error, retry } = useDashboard(activeDatasetId);
  const listState = datasetListState({ loading: datasetsLoading, error: datasetsError, datasets });
  const initialLoading = listState === "loading" || ((overallScope || dataset?.status === "processed") && loading);
  const dashboardReady = !initialLoading;
  usePageTransitionReady(dashboardReady && (pendingScope === null || pendingScope === activeDatasetId));
  useEffect(() => {
    if (dashboardReady && pendingScope === activeDatasetId) setPendingScope(null);
  }, [dashboardReady, pendingScope, activeDatasetId]);
  const displayLabel = getAvatarDetails(user, accountProfile).label;
  const firstName = displayLabel === "User" ? "there" : displayLabel.split(" ")[0];
  const selectScope = (value) => {
    if (value === "all" ? overallScope : !overallScope && value === datasetId) return;
    setPendingScope(value === "all" ? "all" : value);
    if (value === "all") setOverallScope(true);
    else { setOverallScope(false); selectDataset(value); }
  };

  if (listState === "loading") return <><div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>Loading your workspace datasets…</p></div></div><LoadingState rows={3} label="Loading datasets" /></>;
  if (listState === "error") return <><div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>Workspace information is temporarily unavailable.</p></div></div><ErrorState title="Workspace data unavailable" message="We couldn’t retrieve this workspace’s dataset list. Retry, or contact support if the problem continues." onRetry={() => refresh().catch(() => {})} /></>;

  if (listState === "empty") return <>
    <div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>Your workspace is ready for a dataset.</p></div>{["admin", "master_admin"].includes(accountProfile?.app_role) && <div className="heading-actions"><Link to="/datasets" className="primary-button">Add dataset <ArrowRight size={15} /></Link></div>}</div>
    <section className="panel dashboard-api-panel"><div className="panel-heading"><div><h2>No datasets yet</h2><p>Add a dataset to begin exploring learner records and saved results.</p></div><span className="metric-icon violet"><Database size={18} /></span></div>{["admin", "master_admin"].includes(accountProfile?.app_role) && <Link to="/datasets" className="primary-button">Add dataset <ArrowRight size={15} /></Link>}</section>
  </>;

  return <>
    <div className="page-heading dashboard-title"><div><div className="overline">CHURNSHIELD OVERVIEW</div><h1>Welcome, {firstName}</h1><p>{overallScope ? "All Datasets / Overall Class · " : ""}Summary of persisted learner records and predictions.</p></div><div className="heading-actions">
      <DatasetScopeSelect className="dashboard-dataset-select" hiddenLabel label="Active dataset scope" ariaLabel="Active dataset scope" value={overallScope ? "all" : datasetId} datasets={datasets} onChange={(event) => selectScope(event.target.value)} loading={pendingScope !== null && !(dashboardReady && pendingScope === activeDatasetId)} />
      {accountProfile?.app_role === "admin" && <Link to="/reports" className="primary-button dashboard-export-button"><Download size={15}/> Export overview</Link>}
    </div></div>
    {!overallScope && dataset?.status === "failed" && <ErrorState title="Dataset processing failed" message={dataset.error_summary || "Review the dataset validation results and retry processing."} onRetry={() => refresh().catch(() => {})} />}
    {!overallScope && dataset && dataset.status !== "processed" && dataset.status !== "failed" && <div className="illustrative-banner api-notice"><span className="banner-spark"><Activity size={16} /></span><span><strong>Processing in progress.</strong> Dashboard statistics will appear when this dataset is ready.</span></div>}
    {(overallScope || dataset?.status === "processed") && <>
      {loading && <LoadingState rows={2} label="Loading dataset summary" />}
      {error && <ErrorState title="Dashboard unavailable" message="The saved summary could not be loaded. Your dataset remains selected." onRetry={retry} />}
      {!loading && !error && data && <>
        <section className="metrics-grid dashboard-summary-grid" aria-label={overallScope ? "Overall workspace summary" : "Dataset summary"}>
          <Metric Icon={UsersRound} label="Learner-course records" value={data.total_learner_records.toLocaleString()} note="Open Learner Analytics" to={overallScope ? "/learners?scope=all" : "/learners"} />
          <RiskAnalysisMetric data={data} destination={overallScope ? "/early-warning?scope=all" : `/early-warning?dataset_id=${encodeURIComponent(datasetId)}`}/>
          <Metric Icon={Database} tone="green" label="Datasets included" value={Number(data.dataset_count ?? (overallScope ? 0 : 1)).toLocaleString()} note={overallScope ? "Processed datasets in this workspace" : "Selected dataset"} />
        </section>
        <RiskDistributionChart key={`risk-${activeDatasetId}-${JSON.stringify(data.risk_distribution ?? null)}`} distribution={data.risk_distribution} />
        {overallScope && data.dataset_comparison?.length > 0 && <section className="panel dataset-comparison-panel"><div className="panel-heading"><div><h2>Dataset-wise comparison</h2><p>Aggregated from each processed dataset’s persisted summary.</p></div></div><div className="table-scroll"><table className="learner-table"><thead><tr><th>Dataset</th><th>Learner-course records</th><th>Predictions</th><th>Coverage</th><th>Low risk</th><th>Medium risk</th><th>High risk</th></tr></thead><tbody>{data.dataset_comparison.map((row) => <tr key={row.dataset_id}><td>{row.dataset_name}</td><td>{row.learner_course_records.toLocaleString()}</td><td>{row.available_predictions.toLocaleString()}</td><td>{row.prediction_coverage == null ? "—" : `${(row.prediction_coverage * 100).toFixed(1)}%`}</td><td>{row.low_risk_count.toLocaleString()}</td><td>{row.medium_risk_count.toLocaleString()}</td><td>{row.high_risk_count.toLocaleString()}</td></tr>)}</tbody></table></div></section>}
      </>}
    </>}
  </>;
}





