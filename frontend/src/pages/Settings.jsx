import { useState } from "react";
import { AlertCircle, Database, UserRound, LogOut, LoaderCircle, RefreshCw } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useDataset } from "../context/DatasetContext";
import PageHeader from "../components/layout/PageHeader";
import { getAvatarDetails } from "../utils/userAvatar";

export default function Settings() {
  const { user, accountProfile, logout } = useAuth(); const { datasets, dataset, loading: datasetsLoading, error: datasetsError, refresh } = useDataset(); const [logoutError, setLogoutError] = useState(""); const [loggingOut, setLoggingOut] = useState(false); const navigate = useNavigate();
  const accountLabel = getAvatarDetails(user, accountProfile).label;
  const updatedAt = dataset?.updated_at || dataset?.uploaded_at;
  const updatedAtLabel = updatedAt && !Number.isNaN(new Date(updatedAt).getTime()) ? new Date(updatedAt).toLocaleString() : "Last updated time unavailable";
  const datasetStatus = dataset?.status || "Unknown status";
  const datasetStatusClass = String(datasetStatus).toLowerCase().replace(/[^a-z0-9_-]/g, "-");
  const leave = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try { await logout(); navigate("/login", { replace: true }); }
    catch { setLogoutError("Could not sign out. Please try again."); }
    finally { setLoggingOut(false); }
  };
  return <><PageHeader title="Settings" subtitle="Manage your workspace data and account."/><div className="settings-page-grid">
    <section className="panel settings-page-card" aria-labelledby="settings-dataset-heading">
      <div className="settings-page-card-heading"><span className="settings-page-icon"><Database size={20}/></span><div><h2 id="settings-dataset-heading">Dataset</h2><p>Your selected workspace dataset.</p></div></div>
      <div className="settings-dataset-content">
        {datasetsLoading ? <div className="settings-data-state" role="status"><span className="settings-state-spinner"/><div><strong>Loading dataset</strong><span>Retrieving workspace information.</span></div></div>
          : datasetsError ? <div className="settings-data-state settings-data-error" role="alert"><AlertCircle size={19}/><div><strong>Dataset information unavailable</strong><span>This does not mean the workspace is empty.</span></div></div>
            : !dataset ? <div className="settings-data-state"><Database size={19}/><div><strong>No dataset selected</strong><span>Select or upload a dataset to use this workspace.</span></div></div>
              : <div className="settings-dataset-summary"><strong className="settings-dataset-name">{dataset.dataset_name || "Selected dataset"}</strong><span className={`settings-status settings-status-${datasetStatusClass}`}>{datasetStatus}</span><span className="settings-updated">Last updated {updatedAtLabel}</span></div>}
      </div>
      <div className="settings-card-footer"><Link className="secondary-button" to="/datasets">View dataset details</Link>{datasetsError && <button className="secondary-button settings-retry-button" type="button" onClick={() => refresh().catch(() => {})}><RefreshCw size={14}/>Retry</button>}</div>
    </section>
    <section className="panel settings-page-card" aria-labelledby="settings-account-heading">
      <div className="settings-page-card-heading"><span className="settings-page-icon"><UserRound size={20}/></span><div><h2 id="settings-account-heading">Account</h2><p>Your authenticated ChurnShield account.</p></div></div>
      <div className="settings-account-summary"><span className="settings-account-avatar" aria-hidden="true">{getAvatarDetails(user, accountProfile).initials}</span><div><strong>{accountLabel || "Account name unavailable"}</strong><span>{user?.email || "Email unavailable"}</span><small>Profile details are read-only here.</small></div></div>
      {logoutError && <p className="settings-logout-error" role="alert">{logoutError}</p>}
      <div className="settings-card-footer"><button type="button" className="settings-logout-button" disabled={loggingOut} aria-busy={loggingOut} onClick={leave}>{loggingOut ? <LoaderCircle className="logout-spinner" size={16}/> : <LogOut size={16}/>}<span>{loggingOut ? "Signing out…" : "Log out of ChurnShield"}</span></button></div>
    </section>
  </div></>;
}
