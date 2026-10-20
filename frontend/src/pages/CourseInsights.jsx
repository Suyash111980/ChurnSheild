import { BookOpen, Activity, ChartNoAxesCombined } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import { useDashboard } from "../hooks/useDashboard";
import { useDataset } from "../context/DatasetContext";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";

export default function CourseInsights() {
  const { dataset } = useDataset();
  const { data, loading, error, retry } = useDashboard();
  return <><PageHeader eyebrow="COURSE PERFORMANCE" title="Course Insights" subtitle={`Course-level insights for ${dataset?.dataset_name || "the selected dataset"}.`}/>
    {loading && <LoadingState rows={2} label="Loading course insights"/>}
    {error && <ErrorState title="Course insights unavailable" message="The selected dataset summary could not be loaded." onRetry={retry}/>}
    {data && <section className="course-insights-grid">
      <article className="panel withdrawal-panel"><div className="panel-heading"><div><h2>Dataset coverage</h2><p>Verified records in the selected dataset</p></div><BookOpen size={18}/></div><div className="course-insight-summary"><strong>{data.total_learner_records.toLocaleString()}</strong><span>learner-course records</span><strong>{data.course_presentation_count.toLocaleString()}</strong><span>course-presentation combinations</span></div></article>
      <article className="panel course-health"><div className="panel-heading"><div><h2>Course health</h2><p>Per-course metrics require a grouped course API.</p></div><Activity size={18}/></div><div className="course-insight-unavailable">No course-specific health results are available for this dataset.</div></article>
      <article className="panel weekly-panel"><div className="panel-heading"><div><h2>Weekly course engagement</h2><p>Time-series activity is not included in the current API.</p></div><ChartNoAxesCombined size={18}/></div><div className="course-insight-unavailable">Engagement trends are unavailable; no illustrative trend line is shown.</div></article>
    </section>}
  </>;
}
