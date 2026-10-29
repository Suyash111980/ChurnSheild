import { useEffect, useMemo, useState } from "react";
import { Sparkles } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { getLearner, getLearners } from "../services/learnerService";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import { datasetScopeParams } from "../utils/datasetScope";
import { contributionBar, contributionDirection, featureLabel, formatContribution, formatObservedValue, rankContributions } from "../utils/rootCausePresentation.js";
import { useBeginDataTransition, usePageTransitionReady } from "../context/NavigationTransitionContext";
import DatasetScopeSelect from "../components/common/DatasetScopeSelect";

function displayRisk(value) { const text = String(value || "Unavailable"); return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase(); }
function formatSavedAt(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }); }

export default function RootCause() {
  const { datasets, datasetId: activeDatasetId, loading: datasetsLoading } = useDataset();
  const beginDataTransition = useBeginDataTransition();
  const [params, setParams] = useSearchParams();
  const scope = params.get("scope") === "all" ? "all" : params.get("dataset_id") || activeDatasetId || "";
  const search = params.get("q") || "";
  const [draftSearch, setDraftSearch] = useState(search);
  const [list, setList] = useState({ scope: null, learners: [], loading: false, error: null });
  const [selected, setSelected] = useState(null);
  const [profileRequest, setProfileRequest] = useState({ learnerId: null, datasetId: null, profile: null, loading: false, error: null });
  const [reload, setReload] = useState(0);
  const [pendingScope, setPendingScope] = useState(null);

  useEffect(() => setDraftSearch(search), [search]);
  useEffect(() => {
    let active = true;
    setSelected(null);
    if (!scope) { setList({ scope: null, learners: [], loading: false, error: null }); return () => { active = false; }; }
    setList({ scope, learners: [], loading: true, error: null });
    getLearners({ ...datasetScopeParams(scope, { limit: 100, offset: 0, q: search, sort: "latest_risk_probability", direction: "desc" }) })
      .then((page) => { if (active) { const rows = page.data || []; setList({ scope, learners: rows, loading: false, error: null }); setSelected(rows[0] || null); } })
      .catch((error) => { if (active) setList({ scope, learners: [], loading: false, error }); });
    return () => { active = false; };
  }, [scope, search, reload]);

  useEffect(() => {
    let active = true;
    if (!selected) { setProfileRequest({ learnerId: null, datasetId: null, profile: null, loading: false, error: null }); return () => { active = false; }; }
    const selectedDatasetId = selected.dataset_id || (scope === "all" ? null : scope);
    if (!selectedDatasetId) return () => { active = false; };
    setProfileRequest({ learnerId: selected.id, datasetId: selectedDatasetId, profile: null, loading: true, error: null });
    getLearner(selected.id, selectedDatasetId)
      .then((profile) => { if (active) setProfileRequest({ learnerId: selected.id, datasetId: selectedDatasetId, profile, loading: false, error: null }); })
      .catch((error) => { if (active) setProfileRequest({ learnerId: selected.id, datasetId: selectedDatasetId, profile: null, loading: false, error }); });
    return () => { active = false; };
  }, [selected, scope]);

  const currentList = list.scope === scope;
  const learners = currentList ? list.learners : [];
  const listLoading = Boolean(scope) && (!currentList || list.loading);
  const error = currentList ? list.error : null;
  const profileCurrent = profileRequest.learnerId === selected?.id && profileRequest.datasetId === (selected?.dataset_id || (scope === "all" ? null : scope));
  const profile = profileCurrent ? profileRequest.profile : null;
  const profileLoading = Boolean(selected) && (!profileCurrent || profileRequest.loading);
  const selectedDatasetId = selected?.dataset_id || (scope === "all" ? null : scope);
  const scopeDataReady = !datasetsLoading && !listLoading && (!selected || !selectedDatasetId || (profileCurrent && !profileRequest.loading));
  usePageTransitionReady(scopeDataReady && (pendingScope === null || pendingScope === scope));
  useEffect(() => {
    if (scopeDataReady && pendingScope === scope) setPendingScope(null);
  }, [scopeDataReady, pendingScope, scope]);
  const profileError = profileCurrent ? profileRequest.error : null;
  const explanations = Array.isArray(profile?.risk_explanations) ? profile.risk_explanations : [];
  const rankedExplanations = useMemo(() => rankContributions(explanations), [explanations]);
  const maxMagnitude = Math.max(0, ...rankedExplanations.map((item) => Math.abs(Number(item.contribution) || 0)));
  const strongest = rankedExplanations[0] || null;
  const learner = profile?.learner;
  const prediction = profile?.latest_prediction;
  const features = profile?.latest_feature_snapshot?.features;
  const setScope = (value) => {
    if (value === scope) return;
    setPendingScope(value);
    beginDataTransition();
    setParams((current) => { const next = new URLSearchParams(current); next.delete("offset"); if (value === "all") { next.set("scope", "all"); next.delete("dataset_id"); } else { next.delete("scope"); if (value) next.set("dataset_id", value); else next.delete("dataset_id"); } return next; });
  };
  const applySearch = (event) => { event.preventDefault(); setParams((current) => { const next = new URLSearchParams(current); if (draftSearch.trim()) next.set("q", draftSearch.trim()); else next.delete("q"); return next; }); };

  return <><PageHeader eyebrow="EXPLAINABLE ANALYSIS" title="Root Cause Analysis" />
    <section className="panel analysis-controls">
      <DatasetScopeSelect className="analysis-dataset-scope" value={scope} datasets={datasets} onChange={(event) => setScope(event.target.value)} loading={pendingScope !== null && !(scopeDataReady && pendingScope === scope)} label="Dataset" ariaLabel="Analysis dataset" />
      <form onSubmit={applySearch}><label htmlFor="root-cause-search">Search learner</label><input id="root-cause-search" type="search" value={draftSearch} onChange={(event) => setDraftSearch(event.target.value)} placeholder="Learner ID or course"/><button className="secondary-button" type="submit">Search</button></form>
      {!listLoading && !error && learners.length > 0 && <label>Learner record<select aria-label="Select learner record" value={selected?.id || ""} onChange={(event) => setSelected(learners.find((row) => row.id === event.target.value) || null)}>{learners.map((row) => <option key={row.id} value={row.id}>{row.latest_risk_category === "high" ? "High risk · " : ""}{row.student_name || `Learner ${row.id_student}`} · {row.code_module} · {row.code_presentation}{row.latest_risk_probability == null ? " · no prediction" : ` · ${(Number(row.latest_risk_probability) * 100).toFixed(1)}%`}</option>)}</select></label>}
    </section>
    {listLoading && <LoadingState rows={3} label="Loading learner records"/>}
    {error && <ErrorState title="Analysis data unavailable" message="Learner records could not be retrieved." onRetry={() => setReload((value) => value + 1)}/>}
    {!listLoading && !error && learners.length === 0 && <EmptyState title="No learner records" message="No persisted learners match this dataset and search."/>}
    {profileLoading && <LoadingState rows={2} label="Loading saved prediction details"/>}
    {profileError && <ErrorState title="Saved prediction details unavailable" message="The learner profile could not be retrieved." onRetry={() => setReload((value) => value + 1)}/>}
    {profile && <>
      <section className="analysis-grid">
        <article className="panel score-card"><div className="panel-heading"><h2>Risk summary</h2>{prediction?.risk_category ? <span className={`risk-badge risk-${String(prediction.risk_category).toLowerCase()}`}><i/>{prediction.risk_category}</span> : <span className="status-badge status-inactive"><i/>No prediction</span>}</div><strong className="risk-score">{prediction?.risk_probability == null ? "—" : `${(prediction.risk_probability * 100).toFixed(1)}%`}</strong><span className="score-caption">Predicted Churn Risk</span><div className="score-details"><div><span>Risk Level</span><strong>{displayRisk(prediction?.risk_category)}</strong></div><div><span>Learner ID</span><strong>{learner?.id_student || "Unavailable"}</strong></div><div><span>Course</span><strong>{learner?.code_module || "—"} · {learner?.code_presentation || "—"}</strong></div><div><span>Model version</span><strong title={prediction?.model_version || undefined}>{prediction?.model_version || "No saved prediction"}</strong></div>{prediction?.created_at && <div><span>Prediction saved</span><strong>{formatSavedAt(prediction.created_at)}</strong></div>}<div><span>Largest Model Contribution</span><strong>{strongest ? featureLabel(strongest.feature_name) : "Not available"}</strong></div></div></article>
        <article className="panel feature-card"><div className="panel-heading"><div><h2>Persisted feature contributions</h2><p>Feature contributions indicate which recorded inputs influenced this model prediction and in which direction. They describe model behavior, not proven causes of learner churn.</p></div></div>{explanations.length ? <><div className="contribution-legend" aria-label="Contribution direction legend"><span><i className="positive-swatch"/> Positive · toward predicted withdrawal</span><span><i className="negative-swatch"/> Negative · away from predicted withdrawal</span><span>Bar length is relative to the largest contribution shown; it is not a percentage.</span></div><div className="feature-bars">{rankedExplanations.map((item) => { const numeric = Number(item.contribution); const direction = contributionDirection(numeric); const magnitude = contributionBar(numeric, maxMagnitude); const positive = direction.kind === "positive"; const negative = direction.kind === "negative"; return <div className="feature-row" key={item.id || item.feature_name}><div className="feature-copy"><strong>{featureLabel(item.feature_name)}</strong><small>Observed value: {formatObservedValue(item.feature_name, item.feature_value)}</small></div><div className="contribution-visual" role="img" aria-label={`${featureLabel(item.feature_name)} contribution ${formatContribution(item.contribution)}. ${direction.label}.`}><span className={`contribution-bar ${positive ? "positive" : negative ? "negative" : "neutral"}`} style={{ width: `${magnitude}%` }}/></div><div className="contribution-value"><strong title={`Full stored value: ${String(item.contribution)}`}>{formatContribution(item.contribution)}</strong><small className={direction.kind}>{direction.label}</small></div></div>; })}</div><details className="technical-explanations"><summary>Inspect exact stored values</summary><div className="technical-table-wrap"><table><thead><tr><th>Feature key</th><th>Observed value (stored)</th><th>Contribution (full precision)</th></tr></thead><tbody>{rankedExplanations.map((item) => <tr key={`raw-${item.id || item.feature_name}`}><td><code>{item.feature_name}</code></td><td><code>{item.feature_value === undefined ? "undefined" : JSON.stringify(item.feature_value)}</code></td><td><code>{String(item.contribution)}</code></td></tr>)}</tbody></table></div></details></> : <div className="dashboard-api-note"><span><Sparkles size={18}/></span><p>{prediction ? "No persisted explanation records are available for this prediction." : "No saved prediction or explanation is available for this learner."}</p></div>}<details className="contribution-help"><summary>How to read these values</summary><dl><div><dt>Observed value</dt><dd>The value recorded for this learner for the feature.</dd></div><div><dt>Contribution score</dt><dd>The feature's contribution to this individual prediction under the saved SHAP explanation. It is not automatically a percentage or a direct change in churn probability.</dd></div><div><dt>Direction</dt><dd>The explainer selects class 1, documented as Withdrawn. Positive SHAP values move the model output toward that class; negative values move it away. This describes model output, not causation.</dd></div></dl></details>
          {features && typeof features === "object" && <details className="profile-all-explanations"><summary>View persisted feature snapshot</summary><dl>{Object.entries(features).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value == null ? "Missing" : JSON.stringify(value)}</dd></div>)}</dl></details>}
        </article>
      </section>
      <section className="panel insight-panel"><h2>Saved recommendations</h2>{profile.recommendations?.length ? <ul>{profile.recommendations.map((item) => <li key={item.id}><strong>{item.action || "Recommendation"}</strong> · {item.status || "Status unavailable"} — {item.reason || "No persisted rationale"}</li>)}</ul> : <p>No persisted recommendations are associated with this learner and dataset.</p>}</section>
    </>}
  </>;
}
