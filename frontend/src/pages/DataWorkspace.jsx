import { AlertCircle, Database, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { useDataset } from "../context/DatasetContext";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";
import PageHeader from "../components/layout/PageHeader";

export default function DataWorkspace() {
  const { dataset, loading, error, refresh } = useDataset();
  usePageTransitionReady(!loading);

  const updatedAt = dataset?.updated_at || dataset?.uploaded_at;
  const updatedAtLabel = updatedAt && !Number.isNaN(new Date(updatedAt).getTime())
    ? new Date(updatedAt).toLocaleString()
    : "Last updated time unavailable";
  const status = dataset?.status || "Unknown status";
  const statusClass = String(status).toLowerCase().replace(/[^a-z0-9_-]/g, "-");

  return <>
    <PageHeader title="Data Workspace" subtitle="View and manage the dataset selected for your workspace." />
    <section className="panel settings-page-card data-workspace-card" aria-labelledby="workspace-dataset-heading">
      <div className="settings-page-card-heading">
        <span className="settings-page-icon"><Database size={22} /></span>
        <div><h2 id="workspace-dataset-heading">Dataset</h2><p>Your selected workspace dataset.</p></div>
      </div>
      <div className="settings-dataset-content">
        {loading ? (
          <div className="settings-data-state" role="status"><span className="settings-state-spinner" /><div><strong>Loading dataset</strong><span>Retrieving workspace information.</span></div></div>
        ) : error ? (
          <div className="settings-data-state settings-data-error" role="alert"><AlertCircle size={19} /><div><strong>Dataset information unavailable</strong><span>Check your connection and try again.</span></div></div>
        ) : !dataset ? (
          <div className="settings-data-state"><Database size={19} /><div><strong>No dataset selected</strong><span>Select or upload a dataset to use this workspace.</span></div></div>
        ) : (
          <div className="settings-dataset-summary">
            <strong className="settings-dataset-name">{dataset.dataset_name || "Selected dataset"}</strong>
            <span className={`settings-status settings-status-${statusClass}`}>{status}</span>
            <span className="settings-updated">Last updated {updatedAtLabel}</span>
          </div>
        )}
      </div>
      <div className="settings-card-footer">
        {error ? (
          <button className="secondary-button settings-retry-button" type="button" onClick={() => refresh().catch(() => {})}><RefreshCw size={14} />Retry</button>
        ) : (
          <Link className="secondary-button" to="/datasets">{dataset ? "View dataset details" : "Select a dataset"}</Link>
        )}
      </div>
    </section>
  </>;
}
