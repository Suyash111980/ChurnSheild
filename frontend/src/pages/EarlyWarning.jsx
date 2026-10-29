import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, ChevronLeft, ChevronRight, Download, Search, ShieldAlert, UsersRound } from "lucide-react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { getEarlyWarnings } from "../services/recommendationService";
import { getDashboardSummary } from "../services/dashboardService";
import { EARLY_WARNING_PAGE_SIZE, earlyWarningSummary, nextEarlyWarningOffset, previousEarlyWarningOffset } from "../utils/earlyWarningPagination.js";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import { describeEarlyWarningEvidence, getEarlyWarningEvidenceItems, summarizeEarlyWarningEvidence } from "../utils/earlyWarningEvidence";
import DatasetScopeSelect from "../components/common/DatasetScopeSelect";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";

function Kpi({ Icon, tone, value, label, sub }) { return <article className="metric-card compact-kpi"><span className={`metric-icon ${tone}`}><Icon size={18}/></span><strong>{value}</strong><span>{label}</span>{sub && <small>{sub}</small>}</article>; }
function riskClass(value) { return ["low", "medium", "high"].includes(String(value).toLowerCase()) ? `risk-${String(value).toLowerCase()}` : ""; }
function csvCell(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }
function rootCauseReviewPath(row, scope) {
  const params = new URLSearchParams();
  if (row.dataset_id) params.set("dataset_id", row.dataset_id);
  else if (scope === "all") params.set("scope", "all");
  else if (scope) params.set("dataset_id", scope);
  const learnerId = row.id_student ?? row.external_learner_id;
  if (learnerId != null) params.set("q", String(learnerId));
  return `/root-cause?${params.toString()}`;
}
function evidenceValue(value) {
  if (value == null) return "Unavailable";
  if (typeof value === "string") return value;
  try { return JSON.stringify(value); } catch { return "Unavailable"; }
}
function warningErrorMessage(error) {
  const status = Number(error?.status ?? error?.message?.match(/\((\d{3})\)/)?.[1]);
  if (status === 401) return "Your session may have expired. Sign in again to review saved risk records.";
  if (status === 403) return "Your account is not authorized to review this workspace’s records.";
  if (status === 404) return "The selected dataset is not available in this workspace.";
  if (status === 422) return error?.detail || "The dataset scope or filters were rejected. Choose a valid scope and retry.";
  if (status >= 500) return "The early-warning service or database is temporarily unavailable.";
  if (status > 0) return error?.detail || `The early-warning request failed with HTTP ${status}.`;
  return "No HTTP response was received. Check that the backend is running and retry.";
}

function EvidenceCell({ row }) {
  const items = getEarlyWarningEvidenceItems(row);
  const summary = summarizeEarlyWarningEvidence(row, 1);
  if (!items.length) return <span className="warning-evidence-empty">No saved evidence</span>;
  return <div className="warning-evidence">
    <ul className="warning-evidence-summary" aria-label="Representative saved signals">{summary.map((item, index) => <li key={`${item.feature_name}-${index}`}>
      <strong>{item.feature_name}</strong>
      <span>Observed: {evidenceValue(item.feature_value)}</span>
      {item.kind === "explanation" && <span>Contribution: {item.contribution > 0 ? "+" : ""}{item.contribution.toFixed(3)}</span>}
    </li>)}</ul>
    {items.length > summary.length && <details>
      <summary>View all {items.length} saved signals</summary>
      <ul>{items.map((item, index) => <li key={`${item.feature_name}-${index}`}>
      <strong>{item.feature_name}</strong>
      <span>Observed: {evidenceValue(item.feature_value)}</span>
      {item.kind === "explanation" && <span>Contribution: {item.contribution > 0 ? "+" : ""}{item.contribution.toFixed(3)}</span>}
      </li>)}</ul>
    </details>}
  </div>;
}

export default function EarlyWarning() {
  const { datasetId: activeDatasetId, datasets, loading: datasetsLoading } = useDataset();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const overallScope = searchParams.get("scope") === "all";
  const datasetId = overallScope ? "all" : searchParams.get("dataset_id") || activeDatasetId;
  const [request, setRequest] = useState({ datasetId: null, result: null, error: null, loading: false });
  const [summaryRequest, setSummaryRequest] = useState({ datasetId: null, result: null, error: null, loading: false });
  const [reload, setReload] = useState(0);
  const [pendingScope, setPendingScope] = useState(null);
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("");
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    if (!datasetId) { setRequest({ datasetId: null, result: null, error: null, loading: false }); return () => controller.abort(); }
    setRequest({ datasetId, result: null, error: null, loading: true });
    getEarlyWarnings({ ...(datasetId === "all" ? { scope: "all" } : { dataset_id: datasetId }), limit: EARLY_WARNING_PAGE_SIZE, offset, ...(risk ? { risk_category: risk } : {}), ...(query.trim() ? { q: query.trim() } : {}) }, { signal: controller.signal })
      .then((result) => setRequest({ datasetId, result, error: null, loading: false }))
      .catch((error) => { if (!controller.signal.aborted) setRequest({ datasetId, result: null, error, loading: false }); });
    return () => controller.abort();
  }, [datasetId, offset, reload, risk, query]);

  useEffect(() => {
    const controller = new AbortController();
    if (!datasetId) { setSummaryRequest({ datasetId: null, result: null, error: null, loading: false }); return () => controller.abort(); }
    setSummaryRequest({ datasetId, result: null, error: null, loading: true });
    getDashboardSummary(datasetId, { signal: controller.signal }).then((result) => {
      setSummaryRequest({ datasetId, result, error: null, loading: false });
    }).catch((error) => {
      if (!controller.signal.aborted) setSummaryRequest({ datasetId, result: null, error, loading: false });
    });
    return () => controller.abort();
  }, [datasetId, reload]);

  useEffect(() => { setOffset(0); }, [datasetId]);
  const current = request.datasetId === datasetId;
  const result = current ? request.result : null;
  const error = current ? request.error : null;
  const loading = Boolean(datasetId) && (!current || request.loading);
  const rows = useMemo(() => (result?.data || []).filter((row) => {
    const category = String(row.latest_risk_category || "").toLowerCase();
    const text = [row.student_name, row.id_student, row.id, row.code_module, row.code_presentation, row.latest_recommendation?.reason, row.latest_recommendation?.action, describeEarlyWarningEvidence(row), ...(row.latest_explanations || []).map((item) => item.feature_name)].join(" ").toLowerCase();
    return (!risk || category === risk) && (!query.trim() || text.includes(query.trim().toLowerCase()));
  }), [result, query, risk]);
  const summaryIsCurrent = summaryRequest.datasetId === datasetId;
  const summary = summaryIsCurrent ? summaryRequest.result : null;
  const metrics = earlyWarningSummary(summary);
  const summaryLoading = Boolean(datasetId) && (!summaryIsCurrent || summaryRequest.loading);
  const scopeDataReady = !datasetsLoading && !loading && !summaryLoading;
  usePageTransitionReady(scopeDataReady && (pendingScope === null || pendingScope === datasetId));

  useEffect(() => {
    if (scopeDataReady && pendingScope === datasetId) setPendingScope(null);
  }, [scopeDataReady, pendingScope, datasetId]);

  function exportRows() {
    const headers = ["Learner ID", "Course", "Risk", "Probability", "Evidence"];
    const lines = [headers, ...rows.map((row) => [row.id_student || row.id, `${row.code_module || ""} · ${row.code_presentation || ""}`, row.latest_risk_category, row.latest_risk_probability, describeEarlyWarningEvidence(row)])];
    const url = URL.createObjectURL(new Blob([lines.map((line) => line.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "churnshield-early-warning.csv"; anchor.click(); URL.revokeObjectURL(url);
  }
  function selectScope(value) {
    if (value === datasetId) return;
    setPendingScope(value);
    setOffset(0);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value === "all") { next.set("scope", "all"); next.delete("dataset_id"); }
      else { next.delete("scope"); if (value) next.set("dataset_id", value); else next.delete("dataset_id"); }
      return next;
    });
  }

  return <><PageHeader eyebrow="INTERVENTION WORKSPACE" title="Early Warning Center" subtitle="Prioritize outreach using persisted risk results and reviewable evidence."/>
    <DatasetScopeSelect value={overallScope ? "all" : datasetId} datasets={datasets} onChange={(event) => selectScope(event.target.value)} loading={pendingScope !== null && !(scopeDataReady && pendingScope === datasetId)} ariaLabel="Early Warning dataset scope" />
    <div className="page-heading-actions"><button className="secondary-button" disabled={!rows.length} onClick={exportRows}><Download size={15}/> Export visible rows</button></div>
    {!datasetId && <EmptyState title="Select a dataset" message="Choose a processed dataset to review saved risk records and available evidence."/>}
    {loading && <LoadingState rows={4} label="Loading early warning records"/>}
    {error && <ErrorState title="Early warning data unavailable" message={`${warningErrorMessage(error)} No learners are labeled high risk when prediction data is missing.`} onRetry={() => setReload((value) => value + 1)}/>}
    {!loading && !error && result && <>
      <section className="metrics-grid warning-kpis"><Kpi Icon={UsersRound} tone="violet" value={metrics.learnerRecords?.toLocaleString() ?? "—"} label="Learner-course records"/><Kpi Icon={ShieldAlert} tone="blue" value={metrics.savedPredictions?.toLocaleString() ?? "—"} label="Saved predictions" sub={metrics.coverage == null ? "Coverage unavailable" : `${(metrics.coverage * 100).toFixed(1)}% coverage`}/><Kpi Icon={AlertTriangle} tone="amber" value={metrics.high?.toLocaleString() ?? "—"} label="High risk in selected scope"/><Kpi Icon={ShieldAlert} tone="violet" value={metrics.medium?.toLocaleString() ?? "—"} label="Medium risk in selected scope"/><Kpi Icon={ShieldAlert} tone="green" value={metrics.low?.toLocaleString() ?? "—"} label="Low risk in selected scope"/></section>{summaryIsCurrent && summaryRequest.error && <p className="form-subtitle" role="alert">Dataset-wide counts are unavailable; the paginated learner records below may still be reviewed.</p>}
      <section className="panel warning-panel"><div className="queue-heading"><div><span className="priority-tag"><i/> PRIORITY QUEUE</span><h2>Learner-course records</h2><p>All eligible records are paginated below. Only saved predictions receive risk labels.</p></div><div className="review-progress"><span>Showing {result.count ? offset + 1 : 0}–{offset + result.count} of {result.total}</span><i><b style={{ width: result.total ? `${Math.min(100, (offset + result.count) / result.total * 100)}%` : "0%" }}/></i><small>{result.has_more ? "More records available" : "End of available records"}</small></div></div>
        <div className="table-toolbar"><label className="search-box"><Search size={16}/><input aria-label="Search learner or evidence" placeholder="Search learner, course, or evidence…" value={query} onChange={(event) => { setOffset(0); setQuery(event.target.value); }}/></label><div className="filter-row"><select aria-label="Filter risk level" value={risk} onChange={(event) => { setOffset(0); setRisk(event.target.value); }}><option value="">All risk levels</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div></div>
        <p className="table-caption">{rows.length} matching learner-course records <span>High-risk records are prioritized; missing predictions remain unranked.</span></p>
        <div className="table-scroll"><table className="learner-table warning-table"><colgroup><col/><col/><col/><col/><col/><col/><col/></colgroup><thead><tr><th>SR. NO.</th><th>LEARNER ID</th><th>COURSE</th><th>RISK LEVEL</th><th>PROBABILITY</th><th>AVAILABLE EVIDENCE</th><th>PROFILE</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.id}><td className="warning-serial">{offset + index + 1}</td><td><strong className="record-link">{row.id_student != null ? `Learner ${row.id_student}` : `Learner ${row.id}`}</strong>{row.student_name && <small className="warning-learner-name">{row.student_name}</small>}</td><td>{row.code_module || "—"} · {row.code_presentation || "—"}</td><td><span className={`risk-badge ${riskClass(row.latest_risk_category)}`}><i/>{row.latest_risk_category || "Unavailable"}</span></td><td>{row.latest_risk_probability == null ? "—" : `${(row.latest_risk_probability * 100).toFixed(1)}%`}</td><td><EvidenceCell row={row}/></td><td><Link className="secondary-button warning-review-button" to={rootCauseReviewPath(row, datasetId)} state={{ from: `${location.pathname}${location.search}` }}>Review <ArrowRight size={14}/></Link></td></tr>)}</tbody></table>{rows.length === 0 && <EmptyState title="No matching records" message="There are no saved risk results matching these filters."/>}</div>
        {result.total > EARLY_WARNING_PAGE_SIZE && <div className="table-pagination"><span>API records <strong>{result.count ? offset + 1 : 0}–{offset + result.count} of {result.total}</strong></span><div><button className="page-button" disabled={offset === 0} onClick={() => setOffset((value) => previousEarlyWarningOffset(value, result))} aria-label="Previous warning page"><ChevronLeft size={17}/></button><span className="page-number">Page {Math.floor(offset / EARLY_WARNING_PAGE_SIZE) + 1} of {Math.ceil(result.total / EARLY_WARNING_PAGE_SIZE)}</span><button className="page-button" disabled={!result.has_more} onClick={() => setOffset((value) => nextEarlyWarningOffset(value, result))} aria-label="Next warning page"><ChevronRight size={17}/></button></div></div>}
      </section>
    </>}
  </>;
}
