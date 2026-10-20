import { useState } from "react";
import { Bell, Database, ShieldCheck, UserRound, LogOut, LoaderCircle, Monitor, Moon, Sun } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import PageHeader from "../components/layout/PageHeader";
import { useTheme } from "../context/ThemeContext";

function Preference({ title, description, initial = true }) {
  const [enabled, setEnabled] = useState(initial);
  return <div className="preference-row"><div><strong>{title}</strong><span>{description}</span></div><button className={`toggle ${enabled ? "on" : ""}`} role="switch" aria-checked={enabled} aria-label={title} onClick={() => setEnabled(!enabled)}><i/></button></div>;
}

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth(); const [notice, setNotice] = useState(""); const [logoutError, setLogoutError] = useState(""); const [loggingOut, setLoggingOut] = useState(false); const navigate = useNavigate();
  const leave = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try { await logout(); navigate("/login", { replace: true }); }
    catch { setLogoutError("Could not sign out. Please try again."); }
    finally { setLoggingOut(false); }
  };
  return <><PageHeader title="Settings" subtitle="Configure dataset, model review, and notification preferences."/><div className="settings-grid reference-settings-grid">
    <section className="panel settings-panel theme-settings-panel"><div className="settings-section-heading"><span className="settings-icon"><Sun size={18}/></span><div><h2>Appearance</h2><p>Choose how ChurnShield looks on this device.</p></div></div><fieldset className="theme-options"><legend className="sr-only">Color theme</legend>{[["light","Light",Sun],["dark","Dark",Moon],["system","System",Monitor]].map(([value,label,Icon])=><label key={value} className={`theme-option ${theme===value?"selected":""}`}><input type="radio" name="appearance-theme" value={value} checked={theme===value} onChange={()=>setTheme(value)}/><span className="theme-option-icon"><Icon size={17}/></span><span><strong>{label}</strong><small>{value==="system"?"Follow your device preference":`Use ${label.toLowerCase()} appearance`}</small></span></label>)}</fieldset></section>
    <section className="panel settings-panel"><div className="settings-section-heading"><span className="settings-icon"><Database size={18}/></span><div><h2>Dataset</h2><p>Manage the connected learning analytics source.</p></div></div><div className="dataset-line"><div><strong>OULAD demo dataset</strong><span>Illustrative snapshot · read only</span></div><em>Connected</em></div><button className="secondary-button" onClick={()=>setNotice("OULAD demo dataset is an illustrative, read-only sample. No learner data is connected.")}>View dataset details</button></section>
    <section className="panel settings-panel"><div className="settings-section-heading"><span className="settings-icon"><ShieldCheck size={18}/></span><div><h2>Review safeguards</h2><p>Controls for responsible use of model outputs.</p></div></div><div className="preference-list"><Preference title="Require human review" description="Recommendations cannot be actioned automatically."/><Preference title="Show explanation notice" description="Keep non-causation guidance visible."/></div></section>
    <section className="panel settings-panel"><div className="settings-section-heading"><span className="settings-icon"><Bell size={18}/></span><div><h2>Notifications</h2><p>Choose which queue updates need attention.</p></div></div><div className="preference-list"><Preference title="New high-risk records" description="Daily summary of newly flagged records."/><Preference title="Overdue reviews" description="Alert when a suggestion waits more than 48 hours." initial={false}/></div></section>
    <section className="panel settings-panel account-settings"><div className="settings-section-heading"><span className="settings-icon"><UserRound size={18}/></span><div><h2>Account</h2><p>{user?.name} · {user?.email}</p></div></div>{logoutError&&<p className="settings-logout-error" role="alert">{logoutError}</p>}<button className="logout-action" disabled={loggingOut} aria-busy={loggingOut} onClick={leave}>{loggingOut?<LoaderCircle className="logout-spinner" size={15}/>:<LogOut size={15}/>} {loggingOut?"Signing out…":"Log out of ChurnShield"}</button></section>
  </div>{notice&&<div className="notice-message">{notice}<button onClick={()=>setNotice("")}>Dismiss</button></div>}</>;
}
