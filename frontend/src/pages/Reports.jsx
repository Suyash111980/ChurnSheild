import { useEffect, useState } from "react";
import { FileSpreadsheet, Lightbulb, UsersRound } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";
import { useDataset } from "../context/DatasetContext";
import { useAuth } from "../context/AuthContext";
import { getDashboardSummary } from "../services/dashboardService";
import { getRecommendations } from "../services/recommendationService";
import {
  downloadLearnerCsv,
  downloadRecommendationsCsv,
  downloadRiskAnalysisCsv,
} from "../services/reportService";

function ReportCard({ Icon, title, description, available, action, error, busy = false, loading = false, availabilityError = false }) {
  return <article className="panel report-card">
    <span className="report-icon"><Icon size={20}/></span><h2>{title}</h2><p>{description}</p>
    <div className="report-meta"><span>{loading ? "Checking saved records…" : availabilityError ? "Saved record counts could not be verified" : available ? "Available from persisted records" : "No required saved records"}</span><em>{loading ? "Checking" : available ? "Ready" : "Unavailable"}</em></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {busy && <p role="status">Preparing export…</p>}
    <div className="report-buttons"><button className="primary-button" disabled={!available || busy || loading} onClick={action}><FileSpreadsheet size={14}/> {busy ? "Preparing…" : "Export CSV"}</button></div>
  </article>;
}

export default function Reports() {
  const { datasetId, dataset, loading: datasetsLoading } = useDataset();
  const { accountProfile } = useAuth();
  const [availability, setAvailability] = useState({ datasetId: null, loading: false, error: null, learnerCount: 0, predictionCount: 0, recommendationCount: 0 });
  const [busy, setBusy] = useState("");
  const [exportErrors, setExportErrors] = useState({});

  useEffect(() => {
    let active = true;
    if (!datasetId) {
      setAvailability({ datasetId: null, loading: false, error: null, learnerCount: 0, predictionCount: 0, recommendationCount: 0 });
      return () => { active = false; };
    }
    setAvailability({ datasetId, loading: true, error: null, learnerCount: 0, predictionCount: 0, recommendationCount: 0 });
    Promise.all([
      getDashboardSummary(datasetId),
      getRecommendations({ dataset_id: datasetId, limit: 1, offset: 0 }),
    ]).then(([summary, recommendations]) => {
      if (!active) return;
      setAvailability({
        datasetId,
        loading: false,
        error: null,
        learnerCount: Number(summary?.total_learner_records) || 0,
        predictionCount: Number(summary?.learners_with_prediction) || 0,
        recommendationCount: Number(recommendations?.total) || 0,
      });
    }).catch((error) => {
      if (active) setAvailability({ datasetId, loading: false, error, learnerCount: 0, predictionCount: 0, recommendationCount: 0 });
    });
    return () => { active = false; };
  }, [datasetId]);

  async function exportReport(key, action) {
    if (!datasetId || busy) return;
    setBusy(key);
    setExportErrors((previous) => ({ ...previous, [key]: "" }));
    try { await action(datasetId); }
    catch (error) { setExportErrors((previous) => ({ ...previous, [key]: error.message || "The export could not be completed." })); }
    finally { setBusy(""); }
  }

  const current = availability.datasetId === datasetId;
  const loading = Boolean(datasetId) && (!current || availability.loading);
  const counts = current ? availability : null;
  const availabilityError = current ? availability.error : null;
  const hasRecords = Boolean(counts?.learnerCount);
  const hasPredictions = Boolean(counts?.predictionCount);
  const hasRecommendations = Boolean(counts?.recommendationCount);
  const canExport = accountProfile?.app_role === "admin";
  usePageTransitionReady(!datasetsLoading && !loading);

  return <><PageHeader eyebrow="REPORTING CENTER" title="Reports" subtitle="Export saved learner, risk, and retention records for the selected dataset."/>
    <section className="panel report-filters"><div><strong>Selected dataset</strong><p>{dataset?.dataset_name || "Exports are scoped to the active workspace dataset."}</p></div><span className="status-badge status-active"><i/> {datasetId ? "Dataset selected" : "Select a dataset"}</span></section>
    {availabilityError && <p className="form-error" role="alert">Report availability could not be verified. Exports remain disabled until saved record counts can be checked.</p>}
    {!canExport && <p role="status">Report exports are restricted to Admin workspaces.</p>}
    {!datasetId && <p role="status">Select a processed dataset to check which exports contain saved records.</p>}
    <section className="report-grid">
      <ReportCard Icon={UsersRound} title="Learner Summary" description={`${counts?.learnerCount?.toLocaleString() || 0} learner-course records; missing prediction fields remain blank.`} available={canExport && !loading && !availabilityError && hasRecords} loading={loading} availabilityError={Boolean(availabilityError)} action={() => exportReport("learners", downloadLearnerCsv)} error={exportErrors.learners} busy={busy === "learners"}/>
      <ReportCard Icon={FileSpreadsheet} title="Risk Analysis" description={`${counts?.predictionCount?.toLocaleString() || 0} learners have saved prediction results.`} available={canExport && !loading && !availabilityError && hasPredictions} loading={loading} availabilityError={Boolean(availabilityError)} action={() => exportReport("risk", downloadRiskAnalysisCsv)} error={exportErrors.risk} busy={busy === "risk"}/>
      <ReportCard Icon={Lightbulb} title="Retention Recommendations" description={`${counts?.recommendationCount?.toLocaleString() || 0} persisted recommendations are associated with this dataset.`} available={canExport && !loading && !availabilityError && hasRecommendations} loading={loading} availabilityError={Boolean(availabilityError)} action={() => exportReport("recommendations", downloadRecommendationsCsv)} error={exportErrors.recommendations} busy={busy === "recommendations"}/>
    </section>
    <p className="data-footnote"><span>ⓘ</span> Exports contain persisted values only. Missing predictions and recommendations are not filled in or inferred.</p>
  </>;
}
