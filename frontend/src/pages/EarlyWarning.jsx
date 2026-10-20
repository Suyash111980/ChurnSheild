import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, ChevronLeft, ChevronRight, Download, Search, ShieldAlert, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { getEarlyWarnings } from "../services/recommendationService";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import { describeEarlyWarningEvidence, getEarlyWarningEvidenceItems, summarizeEarlyWarningEvidence } from "../utils/earlyWarningEvidence";

function Kpi({ Icon, tone, value, label, sub }) { return <article className="metric-card compact-kpi"><span className={`metric-icon ${tone}`}><Icon size={18}/></span><strong>{value}</strong><span>{label}</span>{sub && <small>{sub}</small>}</article>; }
function riskClass(value) { return ["low", "medium", "high"].includes(String(value).toLowerCase()) ? `risk-${String(value).toLowerCase()}` : ""; }
function csvCell(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }
function evidenceValue(value) {
  if (value == null) return "Unavailable";
  if (typeof value === "string") return value;
  try { return JSON.stringify(value); } catch { return "Unavailable"; }
}

function EvidenceCell({ row }) {
  const items = getEarlyWarningEvidenceItems(row);
  const summary = summarizeEarlyWarningEvidence(row, 3);
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
  const { datasetId } = useDataset();
  const [request, setRequest] = useState({ datasetId: null, result: null, error: null, loading: false });
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("");
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    let active = true;
    if (!datasetId) { setRequest({ datasetId: null, result: null, error: null, loading: false }); return () => { active = false; }; }
    setRequest({ datasetId, result: null, error: null, loading: true });
    getEarlyWarnings({ dataset_id: datasetId, limit: 20, offset })
      .then((result) => { if (active) setRequest({ datasetId, result, error: null, loading: false }); })
      .catch((error) => { if (active) setRequest({ datasetId, result: null, error, loading: false }); });
    return () => { active = false; };
  }, [datasetId, offset, reload]);
  const current = request.datasetId === datasetId;
  const result = current ? request.result : null;
  const error = current ? request.error : null;
  const loading = Boolean(datasetId) && (!current || request.loading);
  const rows = useMemo(() => (result?.data || []).filter((row) => {
    const category = String(row.latest_risk_category || "").toLowerCase();
    const text = [row.student_name, row.id_student, row.id, row.code_module, row.code_presentation, row.latest_recommendation?.reason, row.latest_recommendation?.action, describeEarlyWarningEvidence(row), ...(row.latest_explanations || []).map((item) => item.feature_name)].join(" ").toLowerCase();
    return (!risk || category === risk) && (!query.trim() || text.includes(query.trim().toLowerCase()));
  }), [result, query, risk]);
  const counts = useMemo(() => (result?.data || []).reduce((all, row) => { const category = String(row.latest_risk_category || "").toLowerCase(); if (category in all) all[category] += 1; return all; }, { high: 0, medium: 0, low: 0 }), [result]);

  function exportRows() {
    const headers = ["Learner ID", "Course", "Risk", "Probability", "Evidence"];
    const lines = [headers, ...rows.map((row) => [row.id_student || row.id, `${row.code_module || ""} · ${row.code_presentation || ""}`, row.latest_risk_category, row.latest_risk_probability, describeEarlyWarningEvidence(row)])];
    const url = URL.createObjectURL(new Blob([lines.map((line) => line.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "churnshield-early-warning.csv"; anchor.click(); URL.revokeObjectURL(url);
  }

  return <><PageHeader eyebrow="INTERVENTION WORKSPACE" title="Early Warning Center" subtitle="Prioritize outreach using persisted risk results and reviewable evidence."/>
    <div className="page-heading-actions"><button className="secondary-button" disabled={!rows.length} onClick={exportRows}><Download size={15}/> Export visible rows</button><Link className="primary-button" to="/recommendations">View recommendations <ArrowRight size={15}/></Link></div>
    {!datasetId && <EmptyState title="Select a dataset" message="Choose a processed dataset to review saved risk records and available evidence."/>}
    {loading && <LoadingState rows={4} label="Loading early warning records"/>}
    {error && <ErrorState title="Early warning data unavailable" message="The warning queue could not be loaded. No learners are labeled high risk when prediction data is missing." onRetry={() => setReload((value) => value + 1)}/>}
    {!loading && !error && result && <>
      <section className="metrics-grid warning-kpis"><Kpi Icon={UsersRound} tone="violet" value={result.total.toLocaleString()} label="Records with saved risk results"/><Kpi Icon={AlertTriangle} tone="amber" value={counts.high.toLocaleString()} label="High risk on this page" sub="Review evidence before action"/><Kpi Icon={ShieldAlert} tone="blue" value={counts.medium.toLocaleString()} label="Medium on this page"/><Kpi Icon={ShieldAlert} tone="green" value={counts.low.toLocaleString()} label="Low on this page"/></section>
      <section className="panel warning-panel"><div className="queue-heading"><div><span className="priority-tag"><i/> PRIORITY QUEUE</span><h2>Persisted risk records</h2><p>Missing predictions remain unranked; risk labels come from saved predictions.</p></div><div className="review-progress"><span>Page records: {result.count} of {result.total}</span><i><b style={{ width: result.total ? `${Math.min(100, result.count / result.total * 100)}%` : "0%" }}/></i><small>{result.has_more ? "More records available" : "End of available records"}</small></div></div>
        <div className="table-toolbar"><label className="search-box"><Search size={16}/><input aria-label="Search learner or evidence" placeholder="Search learner, course, or evidence…" value={query} onChange={(event) => setQuery(event.target.value)}/></label><div className="filter-row"><select aria-label="Filter risk level" value={risk} onChange={(event) => setRisk(event.target.value)}><option value="">All risk levels</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div></div>
        <p className="table-caption">{rows.length} matching persisted records <span>Sorted by backend warning order</span></p>
        <div className="table-scroll"><table className="learner-table warning-table"><colgroup><col/><col/><col/><col/><col/><col/></colgroup><thead><tr><th>LEARNER ID</th><th>COURSE</th><th>RISK LEVEL</th><th>PROBABILITY</th><th>AVAILABLE EVIDENCE</th><th>PROFILE</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><strong className="record-link">{row.id_student != null ? `Learner ${row.id_student}` : `Learner ${row.id}`}</strong>{row.student_name && <small className="warning-learner-name">{row.student_name}</small>}</td><td>{row.code_module || "—"} · {row.code_presentation || "—"}</td><td><span className={`risk-badge ${riskClass(row.latest_risk_category)}`}><i/>{row.latest_risk_category || "Unavailable"}</span></td><td>{row.latest_risk_probability == null ? "—" : `${(row.latest_risk_probability * 100).toFixed(1)}%`}</td><td><EvidenceCell row={row}/></td><td><Link className="inline-link" to={`/learners/${encodeURIComponent(row.id)}`}>Review →</Link></td></tr>)}</tbody></table>{rows.length === 0 && <EmptyState title="No matching records" message="There are no saved risk results matching these filters."/>}</div>
        {result.total > 20 && <div className="table-pagination"><span>API records <strong>{offset + 1}–{offset + result.count} of {result.total}</strong></span><div><button className="page-button" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 20))} aria-label="Previous warning page"><ChevronLeft size={17}/></button><span className="page-number">Page {Math.floor(offset / 20) + 1}</span><button className="page-button" disabled={!result.has_more} onClick={() => setOffset((value) => value + 20)} aria-label="Next warning page"><ChevronRight size={17}/></button></div></div>}
      </section>
    </>}
  </>;
}
