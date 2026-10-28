import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMasterAdminOverview } from "../services/masterAdminService";
import { datasetStatusMessage, overviewErrorMessage, overviewMetricValue } from "../utils/masterAdminOverview";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";

export default function MasterAdminDashboard() {
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  usePageTransitionReady(!loading);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getMasterAdminOverview().then((result) => { if (active) setOverview(result); })
      .catch((reason) => { if (active) { setOverview(null); setError(reason); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);
  return <section>
    <header className="admin-requests-heading"><div><p className="form-eyebrow">PLATFORM ADMINISTRATION</p><h1>Super Admin Dashboard</h1><p>Platform account and workspace metadata at a glance.</p></div><Link className="primary-button" to="/admin/users">Review Admin requests</Link></header>
    <p className="master-platform-note master-overview-note">Customer learner records remain private to each Admin’s workspace.</p>
    {error && <div className="form-error" role="alert">{overviewErrorMessage(error)} <button type="button" className="text-button" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
    {loading && <div className="admin-request-loading" role="status">Loading platform overview…</div>}
    <div className="master-platform-grid">
      {[["Admin accounts", overview?.admin_accounts, "purple"], ["Pending approvals", overview?.pending_admin_requests, "amber"], ["Approved admins", overview?.approved_admins, "teal"], ["Rejected requests", overview?.rejected_admins, "rose"], ["Workspaces", overview?.workspaces, "blue"], ["Datasets", overview?.datasets, "violet"]].map(([label, value, accent]) => <article className={`master-platform-card ${accent}`} key={label}><span>{label}</span><strong>{overviewMetricValue(value, { loading })}</strong></article>)}
    </div>
    <section className="master-dataset-status panel"><div className="master-section-heading"><div><h2>Dataset processing</h2><p>Counts by their current persisted processing status.</p></div></div>{datasetStatusMessage(overview, { loading, error: Boolean(error) }) ? <p>{datasetStatusMessage(overview, { loading, error: Boolean(error) })}</p> : <div className="master-status-list">{Object.entries(overview.dataset_status_counts).map(([status, count]) => <div key={status}><span>{status}</span><strong>{count}</strong></div>)}</div>}</section>
  </section>;
}
