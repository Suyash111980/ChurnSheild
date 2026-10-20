import { Clock3, Target, Users } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { useDashboard } from "../hooks/useDashboard";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";

function Kpi({ Icon, label, value, note, tone }) {
  return <article className="panel analytics-kpi"><span className={`analytics-kpi-icon ${tone}`}><Icon size={17}/></span><span>{label}</span><strong>{value}</strong><em>{note}</em></article>;
}

export default function Analytics() {
  const { dataset } = useDataset();
  const { data, loading, error, retry } = useDashboard();
  return <><PageHeader eyebrow="PERFORMANCE & TRENDS" title="Analytics" subtitle={`${dataset?.dataset_name || "Selected dataset"} · verified descriptive statistics and persisted prediction coverage.`}/>
    {loading && <LoadingState rows={2} label="Loading analytics"/>}
    {error && <ErrorState title="Analytics unavailable" message="Dataset statistics could not be retrieved. No sample values are substituted." onRetry={retry}/>}
    {data && <>
      <div className="analytics-kpis">
        <Kpi Icon={Users} tone="blue" label="Learner-course records" value={data.descriptive_statistics.learner_course_records.toLocaleString()} note="Observed in this dataset"/>
        <Kpi Icon={Clock3} tone="violet" label="Course presentations" value={data.descriptive_statistics.course_presentations.toLocaleString()} note="Observed combinations"/>
        <Kpi Icon={Target} tone="green" label="Prediction coverage" value={data.prediction_coverage == null ? "Unavailable" : `${(data.prediction_coverage * 100).toFixed(1)}%`} note={`${data.learners_with_prediction.toLocaleString()} persisted predictions`}/>
      </div>
      <section className="panel course-panel"><div className="panel-heading"><div><h2>Course performance</h2><p>Course-specific engagement and retention breakdowns are not provided by the current API.</p></div></div><div className="dashboard-api-note"><span><Target size={18}/></span><p>Dataset totals above are descriptive statistics. They are not model evaluation metrics and do not imply a course risk trend.</p></div></section>
      <section className="panel"><div className="panel-heading"><div><h2>Model evaluation</h2><p>Offline held-out evaluation is managed separately from live dataset predictions.</p></div></div><p>Workspace-specific evaluation reports are not currently persisted. The platform-level OULAD evaluation, when available, is restricted to Master Admins.</p></section>
    </>}
  </>;
}
