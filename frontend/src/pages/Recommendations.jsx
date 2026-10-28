import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Lightbulb, Sparkles } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { useAuth } from "../context/AuthContext";
import { getRecommendations, updateRecommendationForDataset } from "../services/recommendationService";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import { getRecommendationQueueState, getRecommendationStatusCounts } from "../utils/recommendationPresentation";
import { formatRecommendation } from "../utils/recommendationCopy";
import { datasetScopeParams } from "../utils/datasetScope";
import { useBeginDataTransition, usePageTransitionReady } from "../context/NavigationTransitionContext";

const statusLabels = { pending: "Suggested", in_progress: "In progress", completed: "Completed", dismissed: "Dismissed" };
const statusCards = [["pending", "Suggested", Lightbulb], ["in_progress", "In progress", Clock3], ["completed", "Completed", CheckCircle2], ["dismissed", "Dismissed", Sparkles]];
function riskName(value) { const normalized = String(value || "").toLowerCase(); return ["low", "medium", "high"].includes(normalized) ? normalized : "neutral"; }

export default function Recommendations() {
  const { datasets, datasetId, loading: datasetsLoading } = useDataset();
  const { accountProfile } = useAuth();
  const beginDataTransition = useBeginDataTransition();
  const [searchParams, setSearchParams] = useSearchParams();
  const learnerFilter = searchParams.get("learner_id") || "";
  const requestedDatasetId = searchParams.get("dataset_id");
  const effectiveDatasetId = searchParams.get("scope") === "all" ? "all" : requestedDatasetId || datasetId;
  const [request, setRequest] = useState({ datasetId: null, result: null, error: null, loading: false });
  const [reload, setReload] = useState(0);
  const [pendingScope, setPendingScope] = useState(null);
  const requestSequence = useRef(0);
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("");
  const [workingId, setWorkingId] = useState(null);
  const [updateError, setUpdateError] = useState(null);
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => {
    const requestId = ++requestSequence.current;
    if (!effectiveDatasetId) { setRequest({ datasetId: null, result: null, error: null, loading: false }); return () => {}; }
    const controller = new AbortController();
    setRequest({ datasetId: effectiveDatasetId, result: null, error: null, loading: true });
    getRecommendations({ ...datasetScopeParams(effectiveDatasetId, { ...(learnerFilter ? { learner_id: learnerFilter } : {}), ...(status ? { status } : {}), ...(risk ? { risk_level: risk } : {}) }), limit: 20, offset }, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted || requestId !== requestSequence.current) return;
        setRequest({ datasetId: effectiveDatasetId, result, error: null, loading: false });
      })
      .catch((error) => {
        if (error.name !== "AbortError" && !controller.signal.aborted && requestId === requestSequence.current) {
          setRequest({ datasetId: effectiveDatasetId, result: null, error, loading: false });
        }
      });
    return () => controller.abort();
  }, [effectiveDatasetId, learnerFilter, status, risk, offset]);
  useEffect(() => { setUpdateError(null); setOffset(0); }, [effectiveDatasetId, learnerFilter]);
  useEffect(() => { setOffset(0); }, [status, risk]);
  useEffect(() => load(), [load, reload]);
  const current = request.datasetId === effectiveDatasetId;
  const result = current ? request.result : null;
  const error = current ? request.error : null;
  const loading = Boolean(effectiveDatasetId) && (!current || request.loading);
  const allRows = result?.data || [];
  const rows = allRows;
  const totals = useMemo(() => getRecommendationStatusCounts(result, allRows), [result, allRows]);
  const queueState = getRecommendationQueueState({ datasetId: effectiveDatasetId, loading, error, result });
  usePageTransitionReady(!datasetsLoading && !loading && (pendingScope === null || pendingScope === effectiveDatasetId));
  const canUpdate = accountProfile?.app_role === "admin";
  async function update(item, nextStatus) {
    setWorkingId(item.id);
    setUpdateError(null);
    try { await updateRecommendationForDataset(item.id, item.dataset_id || item.learner?.dataset_id || effectiveDatasetId, nextStatus); setReload((value) => value + 1); }
    catch {
      setUpdateError({ datasetId: effectiveDatasetId });
      setReload((value) => value + 1);
    }
    finally { setWorkingId(null); }
  }
  function selectDatasetScope(value) {
    if (value === effectiveDatasetId) return;
    setPendingScope(value);
    beginDataTransition();
    setOffset(0);
    const next = new URLSearchParams(searchParams);
    if (value === "all") { next.set("scope", "all"); next.delete("dataset_id"); }
    else { next.delete("scope"); if (value) next.set("dataset_id", value); else next.delete("dataset_id"); }
    setSearchParams(next);
  }

  function refreshAfterUpdateError() {
    setUpdateError(null);
    setReload((value) => value + 1);
  }

  return <main className="recommendations-page"><PageHeader eyebrow="RETENTION WORKSPACE" title="Recommendations" subtitle={learnerFilter ? `Review persisted suggestions for learner ${learnerFilter} in the selected dataset.` : "Review persisted retention suggestions and update permitted workflow statuses."}/>
    <div className="recommendations-toolbar"><label className="learner-dataset-scope recommendations-dataset-scope">Dataset scope<select aria-label="Recommendations dataset scope" value={effectiveDatasetId || ""} onChange={(event) => selectDatasetScope(event.target.value)}><option value="all">All Datasets / Overall Class</option>{datasets.map((item) => <option key={item.id} value={item.id}>{item.dataset_name} · {item.status}</option>)}</select></label><div className="page-heading-actions"><button className="secondary-button" onClick={refreshAfterUpdateError} disabled={loading}><Clock3 size={14}/> Refresh queue</button></div></div>
    {learnerFilter && <div className="illustrative-banner api-notice"><span className="banner-spark"><Lightbulb size={16}/></span><span>Queue filtered by learner ID <strong>{learnerFilter}</strong>. The backend still scopes results to the selected dataset.</span><button className="secondary-button recommendation-clear-filter" onClick={() => { const next = new URLSearchParams(searchParams); next.delete("learner_id"); setSearchParams(next); setOffset(0); }}>Show all learners</button></div>}
    {queueState === "loading" && <LoadingState rows={4} label="Loading recommendations"/>}
    {queueState === "error" && <ErrorState title="Recommendations unavailable" message="The persisted recommendation queue could not be loaded." onRetry={() => setReload((value) => value + 1)}/>}
    {updateError?.datasetId === effectiveDatasetId && <ErrorState title="Recommendation status was not confirmed" message="The status update failed or its response was unavailable. Refresh the queue to verify the latest saved status before trying again." onRetry={refreshAfterUpdateError}/>}
    {queueState === "no_dataset" && <EmptyState title="Select a dataset" message="Choose a processed dataset to view its persisted recommendations."/>}
    {queueState === "unavailable" && <ErrorState title="Recommendations unavailable" message="The API response did not contain a recommendation list. No empty state is shown because the result could not be verified." onRetry={() => setReload((value) => value + 1)}/>}
    {queueState === "empty" && <><section className="metrics-grid action-kpis">{statusCards.map(([key, label, Icon]) => <article className="metric-card compact-kpi" key={key}><span className="metric-icon violet"><Icon size={18}/></span><strong>{totals[key]}</strong><span>{label}</span><small>Saved for this dataset{learnerFilter ? " and learner" : ""}</small></article>)}</section><EmptyState title={status ? "No matching recommendations" : "No recommendations yet"} message={status ? "No persisted recommendations match this status filter. The summary above shows all saved statuses for this dataset." : "The API returned no persisted recommendations for this dataset. This page does not generate placeholder actions."}/></>}
    {queueState === "populated" && <>
      <section className="metrics-grid action-kpis">{statusCards.map(([key, label, Icon]) => <article className="metric-card compact-kpi" key={key}><span className="metric-icon violet"><Icon size={18}/></span><strong>{totals[key]}</strong><span>{label}</span><small>Saved for this dataset{learnerFilter ? " and learner" : ""}</small></article>)}</section>
      <section className="panel action-queue"><div className="panel-heading"><div><h2>Retention action queue</h2><p>Showing this page of {result.total} persisted recommendations. Suggestions require human review.</p></div><div className="recommendation-filters"><select aria-label="Filter recommendation status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="" hidden>All statuses</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{status && <button type="button" className="secondary-button recommendation-clear-status" onClick={() => setStatus("")}>All statuses</button>}<select aria-label="Filter recommendation risk level" value={risk} onChange={(event) => setRisk(event.target.value)}><option value="">All risk levels</option><option value="low">Low risk</option><option value="medium">Medium risk</option><option value="high">High risk</option></select></div></div>
        <div className="action-list">{rows.map((item) => {
          const learnerLabel = item.external_learner_id ?? item.id_student ?? item.learner_id;
          const courseLabel = [item.code_module, item.code_presentation].filter(Boolean).join(" · ");
          const itemDatasetId = item.dataset_id || item.learner?.dataset_id || (effectiveDatasetId !== "all" ? effectiveDatasetId : "");
          const presentation = formatRecommendation(item);
          const risk = presentation.risk;
          const hasRisk = Boolean(risk);
          return <article className="action-row" key={item.id}>
            <i className={`action-edge ${riskName(risk)}`}/>
            <div className="action-copy recommendation-copy">
              <strong>{presentation.title}</strong>
              <section><small>Observed reason</small><span>{presentation.reason}</span></section>
              <section><small>Suggested action</small><span>{presentation.action}</span></section>
              {learnerLabel && <small className="action-context">Learner {learnerLabel}{courseLabel ? ` · ${courseLabel}` : ""}</small>}
              <div className="recommendation-context">
                <span className={`recommendation-priority ${riskName(risk)}`}>Priority: {presentation.priority}</span>
                {hasRisk && <span className={`risk-badge ${riskName(risk)}`}>{risk} risk</span>}
                {presentation.probability != null && <span>{(presentation.probability * 100).toFixed(1)}% persisted risk probability</span>}
                {presentation.modelVersion && <span>Model {presentation.modelVersion}</span>}
              </div>
              {(presentation.technicalReason || presentation.ruleId) && <details className="recommendation-evidence"><summary>Recorded technical evidence</summary><code>{presentation.technicalReason || presentation.ruleId}</code></details>}
            </div>
            <span className={`action-status recommendation-status recommendation-status-${item.status || "unknown"}`}>{statusLabels[item.status] || item.status || "Unknown"}</span>
            {item.learner_id && itemDatasetId && <Link className="secondary-button" to={`/learners/${encodeURIComponent(item.learner_id)}?dataset_id=${encodeURIComponent(itemDatasetId)}`}>View learner <ArrowRight size={13}/></Link>}
            {canUpdate && itemDatasetId && item.status === "pending" && <button className="secondary-button" disabled={workingId === item.id} onClick={() => update(item, "in_progress")}>Start review</button>}
            {canUpdate && itemDatasetId && item.status === "in_progress" && <><button className="primary-button" disabled={workingId === item.id} onClick={() => update(item, "completed")}>Complete</button><button className="secondary-button" disabled={workingId === item.id} onClick={() => update(item, "dismissed")}>Dismiss</button></>}
          </article>;
        })}{rows.length === 0 && <EmptyState title="No matching recommendations" message="There are no saved recommendations with this status on this page."/>}</div>
        {result.total > 20 && <div className="table-pagination"><span>API records <strong>{offset + 1}–{offset + result.count} of {result.total}</strong></span><div><button className="page-button" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 20))} aria-label="Previous recommendation page"><ChevronLeft size={17}/></button><span className="page-number">Page {Math.floor(offset / 20) + 1}</span><button className="page-button" disabled={!result.has_more} onClick={() => setOffset((value) => value + 20)} aria-label="Next recommendation page"><ChevronRight size={17}/></button></div></div>}
      </section>
      <p className="data-footnote"><span>ⓘ</span> Recommendations are persisted records; they are not generated by this page.</p>
    </>}
  </main>;
}
