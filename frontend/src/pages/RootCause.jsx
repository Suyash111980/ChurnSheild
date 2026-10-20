import { useEffect, useMemo, useState } from "react";
import { Sparkles } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { getLearner, getLearners } from "../services/learnerService";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";

function formatContribution(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(5) : "Unavailable";
}

export default function RootCause() {
  const { datasetId } = useDataset();
  const [list, setList] = useState({ datasetId: null, learners: [], loading: true, error: null });
  const [selected, setSelected] = useState("");
  const [profileRequest, setProfileRequest] = useState({ datasetId: null, learnerId: null, profile: null, loading: false, error: null });
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    setSelected("");
    if (!datasetId) { setList({ datasetId: null, learners: [], loading: false, error: null }); return () => { active = false; }; }
    setList({ datasetId, learners: [], loading: true, error: null });
    getLearners({ dataset_id: datasetId, limit: 100, offset: 0 })
      .then((page) => { if (active) { const rows = page.data || []; setList({ datasetId, learners: rows, loading: false, error: null }); setSelected(rows[0]?.id || ""); } })
      .catch((error) => { if (active) setList({ datasetId, learners: [], loading: false, error }); });
    return () => { active = false; };
  }, [datasetId, reload]);

  useEffect(() => {
    let active = true;
    if (!selected || !datasetId) { setProfileRequest({ datasetId, learnerId: selected, profile: null, loading: false, error: null }); return () => { active = false; }; }
    setProfileRequest({ datasetId, learnerId: selected, profile: null, loading: true, error: null });
    getLearner(selected, datasetId)
      .then((profile) => { if (active) setProfileRequest({ datasetId, learnerId: selected, profile, loading: false, error: null }); })
      .catch((error) => { if (active) setProfileRequest({ datasetId, learnerId: selected, profile: null, loading: false, error }); });
    return () => { active = false; };
  }, [selected, datasetId]);

  const listCurrent = list.datasetId === datasetId;
  const learners = listCurrent ? list.learners : [];
  const listLoading = Boolean(datasetId) && (!listCurrent || list.loading);
  const error = listCurrent ? list.error : null;
  const profileCurrent = profileRequest.datasetId === datasetId && profileRequest.learnerId === selected;
  const profile = profileCurrent ? profileRequest.profile : null;
  const profileLoading = Boolean(selected && datasetId) && (!profileCurrent || profileRequest.loading);
  const profileError = profileCurrent ? profileRequest.error : null;
  const explanations = profile?.risk_explanations || [];
  const maxMagnitude = Math.max(0, ...explanations.map((item) => Math.abs(Number(item.contribution) || 0)));
  const strongest = useMemo(() => explanations.reduce((best, item) => Math.abs(Number(item.contribution) || 0) > Math.abs(Number(best?.contribution) || 0) ? item : best, null), [explanations]);
  const learner = profile?.learner;
  const prediction = profile?.latest_prediction;

  return <><PageHeader eyebrow="EXPLAINABLE ANALYSIS" title="Root Cause Analysis" subtitle="Review persisted prediction details and available model contributions. Contributions describe model output; they do not establish causation."/>
    {!listLoading && !error && learners.length > 0 && <section className="panel analysis-controls"><label>Learner record<select aria-label="Select learner record" value={selected} onChange={(event) => setSelected(event.target.value)}>{learners.map((row) => <option key={row.id} value={row.id}>{row.student_name || `Learner ${row.id_student}`} · {row.code_module} · {row.code_presentation}</option>)}</select></label><label>Dataset<select aria-label="Selected dataset" value={datasetId} disabled><option value={datasetId}>Active workspace dataset</option></select></label></section>}
    {listLoading && <LoadingState rows={3} label="Loading learner records"/>}
    {error && <ErrorState title="Analysis data unavailable" message="Learner records could not be retrieved." onRetry={() => setReload((value) => value + 1)}/>}
    {!listLoading && !error && learners.length === 0 && <EmptyState title="No learner records" message="Select a dataset with learner records to review saved predictions and explanations."/>}
    {profileLoading && <LoadingState rows={2} label="Loading saved prediction details"/>}
    {profileError && <ErrorState title="Saved prediction details unavailable" message="The learner profile could not be retrieved." onRetry={() => setReload((value) => value + 1)}/>}
    {profile && <>
      <section className="analysis-grid">
        <article className="panel score-card"><div className="panel-heading"><h2>Risk summary</h2>{prediction?.risk_category ? <span className={`risk-badge risk-${String(prediction.risk_category).toLowerCase()}`}><i/>{prediction.risk_category}</span> : <span className="status-badge status-inactive"><i/>Unavailable</span>}</div><strong className="risk-score">{prediction?.risk_probability == null ? "—" : `${(prediction.risk_probability * 100).toFixed(1)}%`}</strong><span className="score-caption">Persisted risk probability</span><div className="score-details"><div><span>Learner ID</span><strong>{learner?.id_student || "Unavailable"}</strong></div><div><span>Course</span><strong>{learner?.code_module || "—"} · {learner?.code_presentation || "—"}</strong></div><div><span>Model</span><strong>{prediction?.model_version || "No saved prediction"}</strong></div><div><span>Top contribution</span><strong>{strongest?.feature_name || "Not available"}</strong></div></div></article>
        <article className="panel feature-card"><div className="panel-heading"><div><h2>Persisted feature contributions</h2><p>Observed values are measured inputs; contributions describe this model output and do not establish causes.</p></div></div>{explanations.length ? <><div className="feature-bars">{explanations.map((item) => { const magnitude = Math.abs(Number(item.contribution) || 0); const upward = Number(item.contribution) > 0; return <div className="feature-row" key={item.id}><span>{item.feature_name}<small>Observed: {item.feature_value == null ? "missing" : JSON.stringify(item.feature_value)}</small></span><i className="feature-track"><b className={upward ? "red" : "teal"} style={{ width: `${maxMagnitude ? magnitude / maxMagnitude * 100 : 0}%` }}/></i><strong title={String(item.contribution)}>{formatContribution(item.contribution)}</strong></div>; })}</div><p className="feature-legend">Contribution direction reflects the stored model explanation. <span>Not causal evidence</span></p></> : <div className="dashboard-api-note"><span><Sparkles size={18}/></span><p>{prediction ? "No persisted explanation records are available for this prediction." : "No saved prediction or explanation is available for this learner."}</p></div>}</article>
      </section>
      <section className="panel insight-panel"><h2>Interpret with care</h2><div className="insight-callout"><Sparkles size={16}/>Model contributions describe associations used by the saved model and do not establish causes.</div><p>Consider relevant context before taking action. Explanations are unavailable when none were persisted for the selected prediction.</p></section>
    </>}
  </>;
}
