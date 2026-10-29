import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowUpRight, ArrowDownRight, Clock3, Sparkles, UserRound } from "lucide-react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import PageHeader from "../components/layout/PageHeader";
import { getLearner } from "../services/learnerService";
import { useDataset } from "../context/DatasetContext";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";
import { buildRiskEvidenceSummary, rankPersistedExplanations, scopeLearnerRecommendations } from "../utils/learnerProfilePresentation";
import { formatRecommendation } from "../utils/recommendationCopy";

const valueOrDash = (value) => value == null || value === "" ? "—" : String(value);
const statusLabels = { pending: "Suggested", in_progress: "In progress", completed: "Completed", dismissed: "Dismissed" };

function formatPercent(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(1)}%` : "Unavailable";
}

function formatContribution(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric > 0 ? "+" : ""}${numeric.toFixed(5)}` : "Unavailable";
}

function formatDate(value) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function getErrorState(error) {
  const status = Number(error?.message?.match(/\((\d{3})\)/)?.[1]);
  if (status === 404) return { title: "Learner record not found", message: "This learner record is not available in the selected dataset. Return to the learner list and choose a record from that dataset." };
  if (status === 401) return { title: "Sign-in required", message: "Your session may have expired. Sign in again to access learner records." };
  if (status === 403) return { title: "Access denied", message: "Your account does not have permission to view this learner." };
  if (status >= 500) return { title: "Profile service unavailable", message: "The server could not load this learner. Try again in a moment." };
  return { title: "Could not load learner profile", message: "Check your connection and try again." };
}

function EvidenceItem({ item, compact = false }) {
  const contribution = Number(item.contribution);
  const direction = contribution > 0 ? "toward withdrawal" : contribution < 0 ? "away from withdrawal" : "neutral direction";
  return <li className="profile-evidence-item">
    <div className="profile-evidence-copy"><strong>{item.feature_name}</strong><span>Observed value: {item.feature_value == null ? "missing" : JSON.stringify(item.feature_value)}</span></div>
    <span className={`contribution-direction ${contribution > 0 ? "increasing" : contribution < 0 ? "decreasing" : "neutral"}`}>
      {contribution > 0 ? <ArrowUpRight size={15}/> : contribution < 0 ? <ArrowDownRight size={15}/> : null}
      <span>{compact ? formatContribution(item.contribution) : `${direction} · ${formatContribution(item.contribution)}`}</span>
    </span>
    {!compact && <span className="profile-full-precision" title="Full precision as returned by the API">Stored value: {String(item.contribution)}</span>}
  </li>;
}

export default function LearnerProfile() {
  const { learnerId } = useParams();
  const { datasetId, loading: datasetsLoading } = useDataset();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const requestedDatasetId = searchParams.get("dataset_id");
  const effectiveDatasetId = requestedDatasetId || datasetId;
  const navigate = useNavigate();
  const [request, setRequest] = useState({ datasetId: null, learnerId: null, record: null, loading: true, error: null });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    if (!effectiveDatasetId) { setRequest({ datasetId: null, learnerId, record: null, loading: false, error: null }); return () => controller.abort(); }
    setRequest({ datasetId: effectiveDatasetId, learnerId, record: null, loading: true, error: null });
    getLearner(learnerId, effectiveDatasetId, { signal: controller.signal })
      .then((result) => {
        if (!result?.learner || typeof result.learner !== "object") throw new Error("The learner profile response was empty or invalid.");
        setRequest({ datasetId: effectiveDatasetId, learnerId, record: result, loading: false, error: null });
      })
      .catch((error) => { if (error.name !== "AbortError") setRequest({ datasetId: effectiveDatasetId, learnerId, record: null, loading: false, error }); });
    return () => controller.abort();
  }, [learnerId, effectiveDatasetId, attempt]);

  const current = request.datasetId === effectiveDatasetId && request.learnerId === learnerId;
  const record = current ? request.record : null;
  const error = current ? request.error : null;
  const loading = Boolean(effectiveDatasetId) && (!current || request.loading);
  usePageTransitionReady(!datasetsLoading && !loading);
  const learner = record?.learner;
  const prediction = record?.latest_prediction;
  const explanations = Array.isArray(record?.risk_explanations) ? record.risk_explanations : [];
  const summaryEvidence = useMemo(() => buildRiskEvidenceSummary(explanations, 3), [explanations]);
  const rankedExplanations = useMemo(() => rankPersistedExplanations(explanations), [explanations]);
  const recommendations = useMemo(() => scopeLearnerRecommendations(record?.recommendations, learner?.id, effectiveDatasetId), [record?.recommendations, learner?.id, effectiveDatasetId]);
  const name = (typeof record?.student_name === "string" && record.student_name.trim()) || (learner?.id_student != null ? `Learner ${learner.id_student}` : `Learner ${learnerId}`);

  return <>
    <Link to={location.state?.from || (requestedDatasetId ? `/learners?dataset_id=${encodeURIComponent(requestedDatasetId)}` : "/learners")} className="profile-back"><ArrowLeft size={15} /> Back to Learners</Link>
    <PageHeader eyebrow="LEARNER PROFILE" title={loading ? "Loading learner…" : error ? "Learner profile" : name} subtitle="Review the saved learner record, prediction evidence, and any persisted support actions." />
    {loading ? <LoadingState rows={5} label="Loading learner profile" /> : error ? <ErrorState {...getErrorState(error)} onRetry={retry} /> : !record ? <EmptyState title="Learner not found" message="The API did not return a learner for this identifier." actionLabel="Return to learners" action={() => navigate("/learners")} /> : <>
      <div className="illustrative-banner api-notice"><span className="banner-spark"><UserRound size={16} /></span><span>Database record <strong>{valueOrDash(learner.id)}</strong> · Learner ID <strong>{valueOrDash(learner.id_student)}</strong>. These identifiers are kept separate from the optional display name.</span></div>

      <section className="profile-summary-grid" aria-label="Learner summary">
        <article className="panel profile-risk-card"><div className="panel-heading"><div><h2>Latest saved prediction</h2><p>Prediction results are not confirmed withdrawal outcomes.</p></div><span className={`risk-badge ${prediction?.risk_category ? `risk-${String(prediction.risk_category).toLowerCase()}` : ""}`}><i/>{prediction?.risk_category || "Unavailable"}</span></div>
          <strong className="profile-risk-probability">{prediction?.risk_probability == null ? "—" : formatPercent(prediction.risk_probability)}</strong>
          <span className="profile-risk-caption">Persisted risk probability</span>
          <dl className="profile-summary-facts"><div><dt>Model</dt><dd>{valueOrDash(prediction?.model_version)}</dd></div><div><dt>Prediction saved</dt><dd>{formatDate(prediction?.created_at)}</dd></div><div><dt>Course</dt><dd>{valueOrDash(learner.code_module)} · {valueOrDash(learner.code_presentation)}</dd></div></dl>
        </article>
        <article className="panel profile-enrollment-card"><div className="panel-heading"><div><h2>Learner and course</h2><p>Fields returned by the selected dataset’s profile API.</p></div></div>
          <dl className="profile-data-grid"><div><dt>Module</dt><dd>{valueOrDash(learner.code_module)}</dd></div><div><dt>Presentation</dt><dd>{valueOrDash(learner.code_presentation)}</dd></div><div><dt>Previous attempts</dt><dd>{valueOrDash(learner.num_of_prev_attempts)}</dd></div><div><dt>Studied credits</dt><dd>{valueOrDash(learner.studied_credits)}</dd></div><div><dt>Age band</dt><dd>{valueOrDash(learner.age_band)}</dd></div><div><dt>Region</dt><dd>{valueOrDash(learner.region)}</dd></div><div><dt>Highest education</dt><dd>{valueOrDash(learner.highest_education)}</dd></div><div><dt>Disability</dt><dd>{valueOrDash(learner.disability)}</dd></div><div><dt>IMD band</dt><dd>{valueOrDash(learner.imd_band)}</dd></div><div><dt>Gender</dt><dd>{valueOrDash(learner.gender)}</dd></div></dl>
        </article>
      </section>

      <section className="panel profile-evidence-panel"><div className="panel-heading"><div><h2>Risk evidence summary</h2><p>Observed values and saved positive-class contributions are shown separately.</p></div><span className="profile-evidence-count">{explanations.length} saved signals</span></div>
        {summaryEvidence.length ? <><ul className="profile-evidence-list profile-summary-evidence">{summaryEvidence.map((item) => <EvidenceItem item={item} compact key={item.id || item.feature_name}/>)}</ul></> : <div className="profile-unavailable-note"><Sparkles size={17}/><p>{prediction ? "No persisted feature explanations are available for this saved prediction." : "No saved prediction or explanation is available for this learner."}{record.latest_feature_snapshot ? " A measured feature snapshot exists, but without persisted explanations no strongest risk evidence can be identified." : ""}</p></div>}
      </section>

      <section className="panel profile-explanation-panel"><div className="panel-heading"><div><h2>Model explanation</h2><p>Ranked persisted contributions describe this model output; they do not establish causes.</p></div></div>
        {rankedExplanations.length ? <><ol className="profile-evidence-list profile-full-evidence">{rankedExplanations.slice(0, 5).map((item) => <EvidenceItem item={item} key={item.id || item.feature_name}/>)}</ol>{rankedExplanations.length > 5 && <details className="profile-all-explanations"><summary>Review all {rankedExplanations.length} saved feature contributions</summary><ol className="profile-evidence-list">{rankedExplanations.map((item) => <EvidenceItem item={item} key={item.id || item.feature_name}/>)}</ol></details>}</> : <p className="profile-empty-copy">There are no persisted contribution records to display.</p>}
      </section>

      <section className="panel profile-recommendations-panel"><div className="panel-heading"><div><h2>Recommendations and support</h2><p>Persisted actions associated with this learner in the selected dataset.</p></div></div>
        {recommendations.length ? <div className="profile-recommendation-list">{recommendations.map((item) => {
          const currentPrediction = prediction?.id && item.prediction_id === prediction.id;
          const presentation = formatRecommendation(item);
          const [evidenceKey, ...evidenceDetail] = String(presentation.technicalReason || "").split(":");
          return <article className="profile-recommendation" key={item.id}><div className="profile-recommendation-heading"><strong>{presentation.title}</strong><span className={`action-status profile-status-${item.status || "unknown"}`}>{statusLabels[item.status] || item.status || "Status unavailable"}</span></div><p><strong>Observed reason:</strong> {presentation.reason}</p><p><strong>Suggested action:</strong> {presentation.action}</p><div className="profile-recommendation-meta"><span className={`profile-priority-chip priority-${String(presentation.priority).toLowerCase()}`}>Priority: {presentation.priority}</span>{presentation.risk && <span className={`profile-risk-chip risk-${String(presentation.risk).toLowerCase()}`}>{presentation.risk} risk{presentation.probability != null ? ` · ${(presentation.probability * 100).toFixed(1)}%` : ""}</span>}<span className="profile-reference-chip">{item.prediction_id ? currentPrediction ? "Related to latest saved prediction" : "Related to another saved prediction" : "Prediction link unavailable"}</span>{item.requires_human_review === true && <span>Human review required</span>}</div>{presentation.technicalReason && <details className="recommendation-evidence"><summary>Recorded technical evidence</summary><code><strong>{evidenceKey}</strong>{evidenceDetail.length ? `: ${evidenceDetail.join(":")}` : ""}</code></details>}</article>;
        })}</div> : <div className="profile-unavailable-note"><Clock3 size={17}/><p>No persisted recommendations are associated with this learner in the selected dataset. The Recommendations page can review saved actions; this profile does not generate new records.</p></div>}
      </section>
    </>}
  </>;
}
