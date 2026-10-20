import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Lightbulb, Sparkles } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { useAuth } from "../context/AuthContext";
import { getRecommendations, updateRecommendationForDataset } from "../services/recommendationService";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import { countRecommendationStatuses, getRecommendationQueueState } from "../utils/recommendationPresentation";

const statusLabels = { pending: "Suggested", in_progress: "In progress", completed: "Completed", dismissed: "Dismissed" };
const statusCards = [["pending", "Suggested", Lightbulb], ["in_progress", "In progress", Clock3], ["completed", "Completed", CheckCircle2], ["dismissed", "Dismissed", Sparkles]];
function riskName(value) { const normalized = String(value || "").toLowerCase(); return ["low", "medium", "high"].includes(normalized) ? normalized : "neutral"; }

export default function Recommendations() {
  const { datasetId } = useDataset();
  const { accountProfile } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const learnerFilter = searchParams.get("learner_id") || "";
  const [request, setRequest] = useState({ datasetId: null, result: null, error: null, loading: false });
  const [reload, setReload] = useState(0);
  const [status, setStatus] = useState("");
  const [workingId, setWorkingId] = useState(null);
  const [updateError, setUpdateError] = useState(null);
  const [offset, setOffset] = useState(0);
  const load = useCallback(() => {
    if (!datasetId) { setRequest({ datasetId: null, result: null, error: null, loading: false }); return () => {}; }
    const controller = new AbortController();
    setRequest({ datasetId, result: null, error: null, loading: true });
    getRecommendations({ dataset_id: datasetId, ...(learnerFilter ? { learner_id: learnerFilter } : {}), limit: 20, offset }, { signal: controller.signal })
      .then((result) => setRequest({ datasetId, result, error: null, loading: false }))
      .catch((error) => { if (error.name !== "AbortError") setRequest({ datasetId, result: null, error, loading: false }); });
    return () => controller.abort();
  }, [datasetId, learnerFilter, offset]);
  useEffect(() => { setUpdateError(null); setOffset(0); setStatus(""); }, [datasetId, learnerFilter]);
  useEffect(() => load(), [load, reload]);
  const current = request.datasetId === datasetId;
  const result = current ? request.result : null;
  const error = current ? request.error : null;
  const loading = Boolean(datasetId) && (!current || request.loading);
  const allRows = result?.data || [];
  const rows = useMemo(() => allRows.filter((item) => !status || item.status === status), [allRows, status]);
  const totals = useMemo(() => countRecommendationStatuses(allRows), [allRows]);
  const queueState = getRecommendationQueueState({ datasetId, loading, error, result });
  const canUpdate = accountProfile?.app_role === "admin";
  async function update(item, nextStatus) {
    setWorkingId(item.id);
    setUpdateError(null);
    try { await updateRecommendationForDataset(item.id, datasetId, nextStatus); setReload((value) => value + 1); }
    catch {
      setUpdateError({ datasetId });
      setReload((value) => value + 1);
    }
    finally { setWorkingId(null); }
  }
  function refreshAfterUpdateError() {
    setUpdateError(null);
    setReload((value) => value + 1);
  }

  return <><PageHeader eyebrow="RETENTION WORKSPACE" title="Recommendations" subtitle={learnerFilter ? `Review persisted suggestions for learner ${learnerFilter} in the selected dataset.` : "Review persisted retention suggestions and update permitted workflow statuses."}/>
    <div className="page-heading-actions"><button className="secondary-button" onClick={refreshAfterUpdateError} disabled={loading}><Clock3 size={14}/> Refresh queue</button></div>
    {learnerFilter && <div className="illustrative-banner api-notice"><span className="banner-spark"><Lightbulb size={16}/></span><span>Queue filtered by learner ID <strong>{learnerFilter}</strong>. The backend still scopes results to the selected dataset.</span><button className="secondary-button recommendation-clear-filter" onClick={() => { setSearchParams({}); setOffset(0); }}>Show all learners</button></div>}
    {queueState === "loading" && <LoadingState rows={4} label="Loading recommendations"/>}
    {queueState === "error" && <ErrorState title="Recommendations unavailable" message="The persisted recommendation queue could not be loaded." onRetry={() => setReload((value) => value + 1)}/>}
    {updateError?.datasetId === datasetId && <ErrorState title="Recommendation status was not confirmed" message="The status update failed or its response was unavailable. Refresh the queue to verify the latest saved status before trying again." onRetry={refreshAfterUpdateError}/>}
    {queueState === "no_dataset" && <EmptyState title="Select a dataset" message="Choose a processed dataset to view its persisted recommendations."/>}
    {queueState === "unavailable" && <ErrorState title="Recommendations unavailable" message="The API response did not contain a recommendation list. No empty state is shown because the result could not be verified." onRetry={() => setReload((value) => value + 1)}/>}
    {queueState === "empty" && <><section className="metrics-grid action-kpis">{statusCards.map(([key, label, Icon]) => <article className="metric-card compact-kpi" key={key}><span className="metric-icon violet"><Icon size={18}/></span><strong>0</strong><span>{label}</span><small>On this API page</small></article>)}</section><EmptyState title="No recommendations yet" message="The API returned no persisted recommendations for this dataset. This page does not generate placeholder actions."/></>}
    {queueState === "populated" && <>
      <section className="metrics-grid action-kpis">{statusCards.map(([key, label, Icon]) => <article className="metric-card compact-kpi" key={key}><span className="metric-icon violet"><Icon size={18}/></span><strong>{totals[key]}</strong><span>{label}</span><small>On this page</small></article>)}</section>
      <section className="panel action-queue"><div className="panel-heading"><div><h2>Retention action queue</h2><p>Showing this page of {result.total} persisted recommendations. Suggestions require human review.</p></div><select aria-label="Filter recommendation status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div className="action-list">{rows.map((item) => {
          const learnerLabel = item.external_learner_id ?? item.id_student ?? item.learner_id;
          const courseLabel = [item.code_module, item.code_presentation].filter(Boolean).join(" · ");
          const risk = item.risk_category || item.prediction?.risk_category;
          const hasRisk = ["low", "medium", "high"].includes(String(risk || "").toLowerCase());
          return <article className="action-row" key={item.id}>
            <i className={`action-edge ${riskName(risk)}`}/>
            <div className="action-copy"><strong>{item.action || "Recommendation"}</strong><span>{item.reason || "No supporting rationale was recorded."}</span>
              {learnerLabel && <small className="action-context">Learner {learnerLabel}{courseLabel ? ` · ${courseLabel}` : ""}</small>}
              {hasRisk && <span className={`risk-badge ${riskName(risk)}`}>{String(risk).toLowerCase()} risk context</span>}
              {item.prediction_id && !hasRisk && <small className="action-context">Related prediction: risk context is not included in this API response.</small>}
            </div>
            <span className="action-status">{statusLabels[item.status] || item.status || "Unknown"}</span>
            {item.learner_id && <Link className="secondary-button" to={`/learners/${encodeURIComponent(item.learner_id)}`}>View learner <ArrowRight size={13}/></Link>}
            {canUpdate && item.status === "pending" && <button className="secondary-button" disabled={workingId === item.id} onClick={() => update(item, "in_progress")}>Start review</button>}
            {canUpdate && item.status === "in_progress" && <><button className="primary-button" disabled={workingId === item.id} onClick={() => update(item, "completed")}>Complete</button><button className="secondary-button" disabled={workingId === item.id} onClick={() => update(item, "dismissed")}>Dismiss</button></>}
          </article>;
        })}{rows.length === 0 && <EmptyState title="No matching recommendations" message="There are no saved recommendations with this status on this page."/>}</div>
        {result.total > 20 && <div className="table-pagination"><span>API records <strong>{offset + 1}–{offset + result.count} of {result.total}</strong></span><div><button className="page-button" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 20))} aria-label="Previous recommendation page"><ChevronLeft size={17}/></button><span className="page-number">Page {Math.floor(offset / 20) + 1}</span><button className="page-button" disabled={!result.has_more} onClick={() => setOffset((value) => value + 20)} aria-label="Next recommendation page"><ChevronRight size={17}/></button></div></div>}
      </section>
      <p className="data-footnote"><span>ⓘ</span> Recommendations are persisted records; they are not generated by this page.</p>
    </>}
  </>;
}
