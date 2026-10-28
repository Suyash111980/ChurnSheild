import { NavLink } from "react-router-dom";
import {
  BookOpen,
  FileText,
  GitBranch,
  LayoutDashboard,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UsersRound,
  X,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { getAvatarDetails } from "../../utils/userAvatar";
import AnimatedAuthLogo from "../common/AnimatedAuthLogo";

const links = [
  ["Dashboard", "/dashboard", LayoutDashboard],
  ["Learner Analytics", "/learners", UsersRound],
  ["Early Warning Center", "/early-warning", ShieldAlert],
  ["Root Cause Analysis", "/root-cause", GitBranch],
  ["Recommendations", "/recommendations", Sparkles],
  ["Course Insights", "/course-insights", BookOpen],
  ["Reports", "/reports", FileText],
];

export default function Sidebar({ open, onClose }) {
  const { user, accountProfile } = useAuth();
  const avatar = getAvatarDetails(user, accountProfile);
  const isMasterAdmin = accountProfile?.app_role === "master_admin";

  return (
    <>
      <button className={`drawer-scrim ${open ? "visible" : ""}`} onClick={onClose} aria-label="Close navigation" />
      <aside className={`sidebar ${open ? "drawer-open" : ""}`}>
        <div className="brand">
          <AnimatedAuthLogo variant="brand" decorative animated className="brand-icon sidebar-logo-mark" />
          <span>Churn<span className="brand-accent">Shield</span></span>
          <button className="mobile-close icon-button" onClick={onClose} aria-label="Close menu"><X size={19} /></button>
        </div>

        {isMasterAdmin ? (
          <nav className="nav-list master-admin-nav" aria-label="Platform administration">
            <NavLink to="/admin/users" end onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <ShieldCheck size={18} /><span>Admin Requests</span>
            </NavLink>
          </nav>
        ) : (
          <>
            <div className="nav-label workspace-label">WORKSPACE</div>
            <nav className="nav-list">
              {links.map(([label, to, Icon, badge]) => (
                <NavLink key={to} to={to} onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                  <Icon size={18} /><span>{label}</span>{badge && <span className="nav-count">{badge}</span>}
                </NavLink>
              ))}
            </nav>
            <div className="nav-label account-label">ACCOUNT</div>
            <nav className="nav-list" aria-label="Account">
              <NavLink to="/settings" onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                <Settings size={18} /><span>Settings</span>
              </NavLink>
            </nav>
          </>
        )}

        {!isMasterAdmin && (
          <div className="sidebar-bottom">
            <div className="profile-row">
              <div className="avatar" role="img" aria-label={`Signed in as ${avatar.label}`}>{avatar.initials.slice(0, 1)}</div>
              <div className="profile-copy"><strong>{avatar.label}</strong><span>{user?.email}</span></div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}



