import { useState } from "react";
import { Bell, Database, LoaderCircle, LogOut, Monitor, Moon, ShieldCheck, Sun, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useDataset } from "../context/DatasetContext";
import PageHeader from "../components/layout/PageHeader";
import { getAvatarDetails } from "../utils/userAvatar";
import { readLocalPreference, writeLocalPreference } from "../utils/localPreferences";
import { useTheme } from "../context/ThemeContext";

function Preference({ title, description, storageKey, initial = true }) {
  const [enabled, setEnabled] = useState(() => readLocalPreference(storageKey, initial));
  function toggle() {
    const next = !enabled;
    writeLocalPreference(storageKey, next);
    setEnabled(next);
  }
  return <div className="preference-row"><div><strong>{title}</strong><span>{description}</span></div><button className={`toggle ${enabled ? "on" : ""}`} role="switch" aria-checked={enabled} aria-label={title} onClick={toggle}><i /></button></div>;
}

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { user, accountProfile, logout } = useAuth();
  const { datasets, dataset, loading: datasetsLoading, error: datasetsError, refresh } = useDataset();
  const [logoutError, setLogoutError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const navigate = useNavigate();
  const accountLabel = getAvatarDetails(user, accountProfile).label;

  const leave = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try { await logout(); navigate("/login", { replace: true }); }
    catch { setLogoutError("Could not sign out. Please try again."); }
    finally { setLoggingOut(false); }
  };

  return <>
    <PageHeader title="Settings" subtitle="Review your account and manage display preferences on this device." />
    <div className="settings-grid reference-settings-grid">
      <section className="panel settings-panel theme-settings-panel">
        <div className="settings-section-heading"><span className="settings-icon"><Sun size={18} /></span><div><h2>Appearance</h2><p>Choose how ChurnShield looks on this device.</p></div></div>
        <fieldset className="theme-options"><legend className="sr-only">Color theme</legend>{[["light", "Light", Sun], ["dark", "Dark", Moon], ["system", "System", Monitor]].map(([value, label, Icon]) => <label key={value} className={`theme-option ${theme === value ? "selected" : ""}`}><input type="radio" name="appearance-theme" value={value} checked={theme === value} onChange={() => setTheme(value)} /><span className="theme-option-icon"><Icon size={17} /></span><span><strong>{label}</strong><small>{value === "system" ? "Follow your device preference" : `Use ${label.toLowerCase()} appearance`}</small></span></label>)}</fieldset>
      </section>
      <section className="panel settings-panel">
        <div className="settings-section-heading"><span className="settings-icon"><Database size={18} /></span><div><h2>Dataset</h2><p>Manage the connected learning analytics source.</p></div></div>
        {datasetsError ? <><div className="dataset-line"><div><strong>Dataset information unavailable</strong><span>This does not mean the workspace is empty.</span></div><em>Unavailable</em></div><button className="secondary-button" onClick={() => refresh().catch(() => {})}>Retry</button></> : datasetsLoading ? <div className="dataset-line" role="status"><div><strong>Loading dataset…</strong><span>Retrieving your workspace metadata.</span></div></div> : datasets.length === 0 ? <div className="dataset-line"><div><strong>No dataset connected</strong><span>Add a dataset to start this workspace.</span></div><em>Empty</em></div> : <div className="dataset-line"><div><strong>{dataset?.dataset_name || "Selected dataset"}</strong><span>{dataset?.updated_at || dataset?.uploaded_at || "Last updated time unavailable"}</span></div><em>{dataset?.status || "Unknown status"}</em></div>}
        <Link className="secondary-button" to="/datasets">View dataset details</Link>
      </section>
      <section className="panel settings-panel">
        <div className="settings-section-heading"><span className="settings-icon"><ShieldCheck size={18} /></span><div><h2>Review safeguards</h2><p>Display preferences for responsible review on this browser.</p></div></div>
        <div className="preference-list"><Preference storageKey="human-review" title="Require human review" description="Recommendations require human review; this preference does not change backend enforcement." /><Preference storageKey="explanation-notice" title="Show explanation notice" description="Keep non-causation guidance visible." /></div>
      </section>
      <section className="panel settings-panel">
        <div className="settings-section-heading"><span className="settings-icon"><Bell size={18} /></span><div><h2>Notifications</h2><p>Browser-local display preferences; no notifications are sent by these settings.</p></div></div>
        <div className="preference-list"><Preference storageKey="new-high-risk" title="New high-risk records" description="Display preference for the warning queue." /><Preference storageKey="overdue-reviews" title="Overdue reviews" description="Display preference for review reminders." initial={false} /></div>
      </section>
      <section className="panel settings-panel account-settings">
        <div className="settings-section-heading"><span className="settings-icon"><UserRound size={18} /></span><div><h2>Account</h2><p>{accountLabel} · {user?.email}</p><span>Profile details are read-only here; account changes are managed through Supabase.</span></div></div>
        {logoutError && <p className="settings-logout-error" role="alert">{logoutError}</p>}
        <button className="logout-action" disabled={loggingOut} aria-busy={loggingOut} onClick={leave}>{loggingOut ? <LoaderCircle className="logout-spinner" size={15} /> : <LogOut size={15} />} {loggingOut ? "Signing out…" : "Log out of ChurnShield"}</button>
      </section>
    </div>
  </>;
}
