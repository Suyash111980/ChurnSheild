import { useCallback, useEffect, useState } from "react";
import { Activity, BookOpen, ChartNoAxesCombined } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";
import { getCourseInsights } from "../services/dashboardService";
import "./CourseInsights.css";

const percent = (value) => value == null ? "—" : `${(value * 100).toFixed(1)}%`;
const probability = (value) => value == null ? "—" : `${(value * 100).toFixed(1)}%`;

export default function CourseInsights() {
  const { dataset, datasetId, loading: datasetsLoading } = useDataset();
  const [result, setResult] = useState({ datasetId: null, data: null, error: null, loading: true });
  const [refreshId, setRefreshId] = useState(0);

  useEffect(() => {
    let active = true;
    if (!datasetId) {
      setResult({ datasetId: null, data: null, error: null, loading: false });
      return () => { active = false; };
    }
    setResult({ datasetId, data: null, error: null, loading: true });
    getCourseInsights(datasetId)
      .then((data) => { if (active) setResult({ datasetId, data, error: null, loading: false }); })
      .catch((error) => { if (active) setResult({ datasetId, data: null, error, loading: false }); });
    return () => { active = false; };
  }, [datasetId, refreshId]);

  const retry = useCallback(() => setRefreshId((value) => value + 1), []);
  const current = result.datasetId === datasetId;
  const loading = Boolean(datasetId) && (!current || result.loading);
  const data = current ? result.data : null;
  usePageTransitionReady(!datasetsLoading && !loading);

  return <div className="course-insights-page">
    <PageHeader eyebrow="COURSE PERFORMANCE" title="Course Insights" subtitle={`Saved prediction coverage and risk by course for ${dataset?.dataset_name || "the selected dataset"}.`} />
    {loading && <LoadingState rows={2} label="Loading course insights" />}
    {current && result.error && <ErrorState title="Course insights unavailable" message="Course summaries could not be loaded from the selected dataset." onRetry={retry} />}
    {!loading && current && !result.error && !datasetId && <div className="course-unavailable" role="status"><strong>Select a dataset</strong><span>Choose a processed dataset to view its saved course predictions.</span></div>}
    {data && <>
      <section className="course-insights-grid" aria-label="Course insights">
        <article className="panel withdrawal-panel">
          <div className="panel-heading"><div><h2>Dataset coverage</h2><p>Records and predictions saved for this dataset</p></div><BookOpen size={18} /></div>
          <div className="course-insight-summary">
            <strong>{data.learner_course_records.toLocaleString()}</strong><span>learner-course records</span>
            <strong>{data.course_presentation_count.toLocaleString()}</strong><span>course presentations</span>
            <strong>{data.learners_with_prediction.toLocaleString()}</strong><span>records with saved predictions</span>
          </div>
        </article>
        <article className="panel course-health">
          <div className="panel-heading"><div><h2>Course health</h2><p>Latest persisted model risk by module and presentation</p></div><Activity size={18} /></div>
          {data.courses.length === 0 ? <div className="course-unavailable" role="status"><strong>No course records found</strong><span>This dataset has no course presentation rows to summarize.</span></div> : <div className="course-insights-table-wrap"><table className="course-insights-table">
            <thead><tr><th scope="col">Course</th><th scope="col">Learners</th><th scope="col">Scored</th><th scope="col">Coverage</th><th scope="col">High risk</th><th scope="col">Mean risk</th></tr></thead>
            <tbody>{data.courses.map((course) => <tr key={`${course.code_module}-${course.code_presentation}`}>
              <th scope="row">{course.code_module} <span>{course.code_presentation}</span></th>
              <td>{course.learner_course_records.toLocaleString()}</td>
              <td>{course.learners_with_prediction.toLocaleString()}</td>
              <td>{percent(course.prediction_coverage)}</td>
              <td>{course.high_risk_count.toLocaleString()}</td>
              <td>{probability(course.average_risk_probability)}</td>
            </tr>)}</tbody>
          </table></div>}
        </article>
        <article className="panel weekly-panel">
          <div className="panel-heading"><div><h2>Weekly course engagement</h2><p>Requires dated VLE activity events</p></div><ChartNoAxesCombined size={18} /></div>
          <div className="weekly-unavailable" role="status"><span className="weekly-empty-icon" aria-hidden="true">↗</span><div><strong>Weekly activity data unavailable</strong><p>The current dataset stores learner-course features and predictions, but not dated VLE interaction events. No trend is inferred from summary features.</p></div></div>
        </article>
      </section>
      
    </>}
  </div>;
}
