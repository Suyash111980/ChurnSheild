import { useState } from "react";
import { FileSpreadsheet, Lightbulb, UsersRound, Download } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import { useDataset } from "../context/DatasetContext";
import { downloadLearnerCsv } from "../services/reportService";

function ReportCard({ Icon, title, description, available, action, error, busy = false }) {
  return <article className="panel report-card"><span className="report-icon"><Icon size={20}/></span><h2>{title}</h2><p>{description}</p><div className="report-meta"><span>{available ? "Available from persisted records" : "Not available"}</span><em>{available ? "Ready" : "Unavailable"}</em></div>{error && <p className="form-error" role="alert">{error}</p>}{busy && <p role="status">Preparing export…</p>}<div className="report-buttons"><button className="primary-button" disabled={!available || busy} onClick={action}><Download size={14}/> {busy ? "Preparing…" : "Export CSV"}</button></div></article>;
}

export default function Reports() {
  const { datasetId } = useDataset();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function download() {
    if (!datasetId || busy) return;
    setBusy(true); setError("");
    try {
      await downloadLearnerCsv(datasetId);
    } catch (reason) { setError(reason.message || "Learner export is unavailable."); }
    finally { setBusy(false); }
  }
  return <><PageHeader eyebrow="REPORTING CENTER" title="Reports" subtitle="Create review-ready exports from the selected dataset."/>
    <section className="panel report-filters"><div><strong>Selected dataset</strong><p>Exports are scoped to the active workspace dataset.</p></div><span className="status-badge status-active"><i/> {datasetId ? "Dataset selected" : "Select a dataset"}</span></section>
    <section className="report-grid">
      <ReportCard Icon={UsersRound} title="Learner Summary" description="Export learner identifiers, course context, and persisted prediction fields." available={Boolean(datasetId)} action={download} error={error} busy={busy}/>
      <ReportCard Icon={FileSpreadsheet} title="Risk Analysis" description="Risk summaries and explanation exports are not available from the current report API." available={false}/>
      <ReportCard Icon={Lightbulb} title="Retention Recommendations" description="Recommendation exports are not available from the current report API." available={false}/>
    </section>
    <p className="data-footnote"><span>ⓘ</span> Only persisted values are exported. Missing prediction fields remain blank; no sample data is included.</p>
  </>;
}
