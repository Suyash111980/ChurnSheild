import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../services/apiClient";
import { datasetStatusMessage, overviewErrorMessage, overviewMetricValue } from "../utils/masterAdminOverview";

export default function MasterAdminDashboard() {
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    apiRequest("/master-admin/overview").then((result) => { if (active) setOverview(result); })
      .catch((reason) => { if (active) { setOverview(null); setError(reason); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);
  return <section>
    <header className="page-header"><div><p className="form-eyebrow">PLATFORM ADMINISTRATION</p><h1>Platform Overview</h1></div><Link className="text-button" to="/admin/users">Review Admin requests</Link></header>
    <p className="form-subtitle">Platform account and workspace metadata only. Customer learner records remain in each Admin’s private workspace.</p>
    {error && <div className="form-error" role="alert">{overviewErrorMessage(error)} <button type="button" className="text-button" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
    {loading && <p role="status">Loading platform overview…</p>}
    <div className="analytics-grid">
      {[["Admin accounts", overview?.admin_accounts], ["Pending requests", overview?.pending_admin_requests], ["Approved Admins", overview?.approved_admins], ["Rejected Admins", overview?.rejected_admins], ["Workspaces", overview?.workspaces], ["Datasets", overview?.datasets]].map(([label, value]) => <article className="settings-panel" key={label}><span>{label}</span><strong>{overviewMetricValue(value, { loading })}</strong></article>)}
      <article className="settings-panel"><h2>Dataset processing</h2>{datasetStatusMessage(overview, { loading, error: Boolean(error) }) ? <p>{datasetStatusMessage(overview, { loading, error: Boolean(error) })}</p> : Object.entries(overview.dataset_status_counts).map(([status, count]) => <p key={status}>{status}: {count}</p>)}</article>
    </div>
  </section>;
}
