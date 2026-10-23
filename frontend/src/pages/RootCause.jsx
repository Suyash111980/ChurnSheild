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

function formatContribution(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(5) : "Unavailable";
}

export default function RootCause() {
  const { datasets, datasetId: activeDatasetId } = useDataset();
  const [params, setParams] = useSearchParams();
  const scope = params.get("scope") === "all" ? "all" : params.get("dataset_id") || activeDatasetId || "";
  const search = params.get("q") || "";
  const [draftSearch, setDraftSearch] = useState(search);
  const [list, setList] = useState({ scope: null, learners: [], loading: false, error: null });
  const [selected, setSelected] = useState(null);
  const [profileRequest, setProfileRequest] = useState({ learnerId: null, datasetId: null, profile: null, loading: false, error: null });
  const [reload, setReload] = useState(0);

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
  const profileError = profileCurrent ? profileRequest.error : null;
  const explanations = Array.isArray(profile?.risk_explanations) ? profile.risk_explanations : [];
  const maxMagnitude = Math.max(0, ...explanations.map((item) => Math.abs(Number(item.contribution) || 0)));
  const strongest = useMemo(() => explanations.reduce((best, item) => Math.abs(Number(item.contribution) || 0) > Math.abs(Number(best?.contribution) || 0) ? item : best, null), [explanations]);
  const learner = profile?.learner;
  const prediction = profile?.latest_prediction;
  const features = profile?.latest_feature_snapshot?.features;
  const setScope = (value) => setParams((current) => { const next = new URLSearchParams(current); next.delete("offset"); if (value === "all") { next.set("scope", "all"); next.delete("dataset_id"); } else { next.delete("scope"); if (value) next.set("dataset_id", value); else next.delete("dataset_id"); } return next; });
  const applySearch = (event) => { event.preventDefault(); setParams((current) => { const next = new URLSearchParams(current); if (draftSearch.trim()) next.set("q", draftSearch.trim()); else next.delete("q"); return next; }); };

  return <><PageHeader eyebrow="EXPLAINABLE ANALYSIS" title="Root Cause Analysis" subtitle="Review persisted prediction details, measured feature values, and saved model contributions. Contributions describe model output and do not establish causation." />
    <section className="panel analysis-controls">
      <label>Dataset<select aria-label="Analysis dataset" value={scope} onChange={(event) => setScope(event.target.value)}><option value="all">All Datasets / Overall Class</option>{datasets.map((item) => <option key={item.id} value={item.id}>{item.dataset_name} · {item.status}</option>)}</select></label>
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
        <article className="panel score-card"><div className="panel-heading"><h2>Risk summary</h2>{prediction?.risk_category ? <span className={`risk-badge risk-${String(prediction.risk_category).toLowerCase()}`}><i/>{prediction.risk_category}</span> : <span className="status-badge status-inactive"><i/>No prediction</span>}</div><strong className="risk-score">{prediction?.risk_probability == null ? "—" : `${(prediction.risk_probability * 100).toFixed(1)}%`}</strong><span className="score-caption">Persisted risk probability</span><div className="score-details"><div><span>Learner ID</span><strong>{learner?.id_student || "Unavailable"}</strong></div><div><span>Course</span><strong>{learner?.code_module || "—"} · {learner?.code_presentation || "—"}</strong></div><div><span>Model</span><strong>{prediction?.model_version || "No saved prediction"}</strong></div><div><span>Top contribution</span><strong>{strongest?.feature_name || "Not available"}</strong></div></div></article>
        <article className="panel feature-card"><div className="panel-heading"><div><h2>Saved feature contributions</h2><p>Observed values are measured inputs; contributions describe this model output and do not establish causes.</p></div></div>{explanations.length ? <><div className="feature-bars">{explanations.map((item) => { const magnitude = Math.abs(Number(item.contribution) || 0); const upward = Number(item.contribution) > 0; return <div className="feature-row" key={item.id}><span>{item.feature_name}<small>Observed: {item.feature_value == null ? "missing" : JSON.stringify(item.feature_value)}</small></span><i className="feature-track"><b className={upward ? "red" : "teal"} style={{ width: `${maxMagnitude ? magnitude / maxMagnitude * 100 : 0}%` }}/></i><strong title={String(item.contribution)}>{formatContribution(item.contribution)}</strong></div>; })}</div><p className="feature-legend">Contribution direction reflects the stored model explanation. <span>Not causal evidence</span></p></> : <div className="dashboard-api-note"><span><Sparkles size={18}/></span><p>{prediction ? "No persisted explanation records are available for this prediction." : "No saved prediction or explanation is available for this learner."}</p></div>}
          {features && typeof features === "object" && <details className="profile-all-explanations"><summary>View persisted feature snapshot</summary><dl>{Object.entries(features).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value == null ? "Missing" : JSON.stringify(value)}</dd></div>)}</dl></details>}
        </article>
      </section>
      <section className="panel insight-panel"><h2>Saved recommendations</h2>{profile.recommendations?.length ? <ul>{profile.recommendations.map((item) => <li key={item.id}><strong>{item.action || "Recommendation"}</strong> · {item.status || "Status unavailable"} — {item.reason || "No persisted rationale"}</li>)}</ul> : <p>No persisted recommendations are associated with this learner and dataset.</p>}<div className="insight-callout"><Sparkles size={16}/>Model contributions describe associations used by the saved model and do not establish causes.</div></section>
    </>}
  </>;
}
