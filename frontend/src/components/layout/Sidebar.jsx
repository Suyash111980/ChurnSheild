import { NavLink, useNavigate } from "react-router-dom";
import { Activity, BarChart3, BookOpen, ChartNoAxesCombined, FileText, GitBranch, LayoutDashboard, LogOut, Settings, ShieldAlert, ShieldCheck, Sparkles, UsersRound, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const links = [
  ["Dashboard", "/dashboard", LayoutDashboard],
  ["Learner Analytics", "/learners", UsersRound],
  ["Early Warning Center", "/early-warning", ShieldAlert, "12"],
  ["Root Cause Analysis", "/root-cause", GitBranch],
  ["Recommendations", "/recommendations", Sparkles],
  ["Course Insights", "/course-insights", BookOpen],
  ["Reports", "/reports", FileText],
];

export default function Sidebar({ open, onClose }) {
  const { user, logout, accountProfile } = useAuth();
  const navigate = useNavigate();
  const leave = () => { logout(); navigate("/login"); };
  return <>
    <button className={`drawer-scrim ${open ? "visible" : ""}`} onClick={onClose} aria-label="Close navigation" />
    <aside className={`sidebar ${open ? "drawer-open" : ""}`}>
      <div className="brand"><div className="brand-icon"><ChartNoAxesCombined size={22} /></div><span>Churn<span className="brand-accent">Shield</span></span><button className="mobile-close icon-button" onClick={onClose} aria-label="Close menu"><X size={19} /></button></div>
      <div className="nav-label workspace-label">WORKSPACE</div>
      <nav className="nav-list">{links.map(([label, to, Icon, badge]) => <NavLink key={to} to={to} onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}><Icon size={18} /><span>{label}</span>{badge && <span className="nav-count">{badge}</span>}</NavLink>)}</nav>
      <div className="nav-label account-label">ACCOUNT</div>
      <nav className="nav-list">
        <NavLink to="/settings" onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}><Settings size={18} /><span>Settings</span></NavLink>
        {accountProfile?.app_role === "admin" && <NavLink to="/admin/users" onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}><ShieldCheck size={18} /><span>Account approvals</span></NavLink>}
      </nav>
      <div className="sidebar-bottom"><div className="plan-card"><div className="plan-icon"><Sparkles size={16} /></div><div><strong>Need a clearer signal?</strong><span>Review the model guide before taking action.</span></div><a href="#guide" onClick={e => e.preventDefault()}>Open responsible AI guide <span>→</span></a></div>
        <div className="profile-row"><div className="avatar">{user?.name?.slice(0, 1).toUpperCase() || "P"}</div><div className="profile-copy"><strong>{user?.name || "Demo user"}</strong><span>{user?.email}</span></div><button className="icon-button logout" title="Log out" aria-label="Log out" onClick={leave}><LogOut size={17} /></button></div>
      </div>
    </aside>
  </>;
}
