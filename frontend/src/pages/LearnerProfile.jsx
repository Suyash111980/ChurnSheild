import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, UserRound } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import PageHeader from "../components/layout/PageHeader";
import { getLearner } from "../services/learnerService";

function valueOrDash(value) {
  return value == null || value === "" ? "—" : String(value);
}

function getErrorState(error) {
  const status = Number(error?.message?.match(/\((\d{3})\)/)?.[1]);
  if (status === 404) return {
    title: "Learner profile endpoint unavailable",
    message: "The backend currently provides a paginated learner list but does not implement GET /learners/{id}. A profile cannot be loaded until that API route is added.",
  };
  if (status === 401) return { title: "Sign-in required", message: "Your session may have expired. Sign in again to access learner records." };
  if (status === 403) return { title: "Access denied", message: "Your account does not have permission to view this learner." };
  if (status >= 500) return { title: "Profile service unavailable", message: "The server could not load this learner. Try again in a moment." };
  return { title: "Could not load learner profile", message: "Check your connection and try again." };
}

export default function LearnerProfile() {
  const { learnerId } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setRecord(null);
    getLearner(learnerId, { signal: controller.signal })
      .then((result) => {
        const learner = result?.data ?? result;
        if (!learner || typeof learner !== "object" || Array.isArray(learner)) {
          throw new Error("The learner profile response was empty or invalid.");
        }
        setRecord(learner);
      })
      .catch((reason) => { if (reason.name !== "AbortError") setError(reason); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [learnerId, attempt]);

  const displayName = typeof record?.student_name === "string" ? record.student_name.trim() : "";
  const name = displayName || (record?.id_student != null ? `Learner ${record.id_student}` : `Learner ${learnerId}`);

  return <>
    <Link to="/learners" className="profile-back"><ArrowLeft size={15} /> Back to Learners</Link>
    <PageHeader eyebrow="LEARNER PROFILE" title={loading ? "Loading learner…" : error ? "Learner profile" : name} subtitle="Profile fields are shown only when supplied by the authenticated backend." />
    {loading ? <LoadingState rows={5} label="Loading learner profile" /> : error ? <ErrorState {...getErrorState(error)} onRetry={retry} /> : !record ? <EmptyState title="Learner not found" message="The API did not return a learner for this identifier." actionLabel="Return to learners" action={() => navigate("/learners")} /> : <>
      <div className="illustrative-banner api-notice"><span className="banner-spark"><UserRound size={16} /></span><span>Database record <strong>{valueOrDash(record.id)}</strong> · Learner ID <strong>{valueOrDash(record.id_student)}</strong>. These identifiers are kept separate from the optional display name.</span></div>
      <section className="panel profile-data-panel">
        <div className="panel-heading"><div><h2>Enrollment context</h2><p>Values returned by the learner profile API</p></div></div>
        <dl className="profile-data-grid">
          <div><dt>Module</dt><dd>{valueOrDash(record.code_module)}</dd></div>
          <div><dt>Presentation</dt><dd>{valueOrDash(record.code_presentation)}</dd></div>
          <div><dt>Highest education</dt><dd>{valueOrDash(record.highest_education)}</dd></div>
          <div><dt>Region</dt><dd>{valueOrDash(record.region)}</dd></div>
          <div><dt>Age band</dt><dd>{valueOrDash(record.age_band)}</dd></div>
          <div><dt>Previous attempts</dt><dd>{valueOrDash(record.num_of_prev_attempts)}</dd></div>
          <div><dt>Studied credits</dt><dd>{valueOrDash(record.studied_credits)}</dd></div>
          <div><dt>Disability</dt><dd>{valueOrDash(record.disability)}</dd></div>
          <div><dt>IMD band</dt><dd>{valueOrDash(record.imd_band)}</dd></div>
          <div><dt>Gender</dt><dd>{valueOrDash(record.gender)}</dd></div>
        </dl>
        <p className="profile-limitation">Risk scores, model explanations, engagement history, and interventions are not included because the current backend profile contract does not provide them.</p>
      </section>
    </>}
  </>;
}
