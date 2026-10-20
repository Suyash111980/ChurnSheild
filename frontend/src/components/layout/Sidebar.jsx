import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import { BookOpen, FileText, GitBranch, LayoutDashboard, PanelLeftClose, PanelLeftOpen, Settings, ShieldAlert, ShieldCheck, Sparkles, UsersRound, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { getAvatarDetails } from "../../utils/userAvatar";
import AnimatedLogo from "../common/AnimatedLogo";

const links = [
  ["Dashboard", "/dashboard", LayoutDashboard],
  ["Learner Analytics", "/learners", UsersRound],
  ["Early Warning Center", "/early-warning", ShieldAlert],
  ["Root Cause Analysis", "/root-cause", GitBranch],
  ["Recommendations", "/recommendations", Sparkles],
  ["Course Insights", "/course-insights", BookOpen],
  ["Reports", "/reports", FileText],
];

export default function Sidebar({ open, onClose, collapsed, onToggleCollapse, inert, menuTriggerRef }) {
  const { user, accountProfile } = useAuth();
  const avatar = getAvatarDetails(user, accountProfile);
  const displayName = avatar.label !== "User" && avatar.label !== user?.email ? avatar.label : "Account";
  const sidebarRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = menuTriggerRef?.current ?? document.activeElement;
    const sidebar = sidebarRef.current;
    sidebar?.querySelector(".mobile-close")?.focus();

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "Tab") {
        const focusable = [...(sidebar?.querySelectorAll('a[href], button:not(:disabled)') ?? [])].filter((element) => element.getClientRects().length > 0);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open, onClose, menuTriggerRef]);

  const navItem = ([label, to, Icon]) => <NavLink
    key={to}
    to={to}
    onClick={onClose}
    title={collapsed ? label : undefined}
    aria-label={label}
    data-tooltip={label}
    className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
  ><Icon size={18} aria-hidden="true"/><span>{label}</span></NavLink>;

  return <>
    <button className={`drawer-scrim ${open ? "visible" : ""}`} onClick={onClose} tabIndex={open ? 0 : -1} aria-hidden={!open} aria-label="Close navigation drawer" />
    <aside ref={sidebarRef} id="primary-sidebar" className={`sidebar${open ? " drawer-open" : ""}${collapsed ? " collapsed" : ""}`} role={open ? "dialog" : undefined} aria-modal={open || undefined} aria-labelledby={open ? "sidebar-brand" : undefined} aria-label={open ? undefined : "Primary navigation"} aria-hidden={inert || undefined} inert={inert || undefined}>
      <div className="brand"><AnimatedLogo variant="sidebar" /><span className="brand-name" id="sidebar-brand">Churn<span className="brand-accent">Shield</span></span><button type="button" className="sidebar-collapse-toggle icon-button" onClick={onToggleCollapse} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} aria-expanded={!collapsed} title={collapsed ? "Expand navigation" : "Collapse navigation"}>{collapsed ? <PanelLeftOpen size={17}/> : <PanelLeftClose size={17}/>}</button><button type="button" className="mobile-close icon-button" onClick={onClose} aria-label="Close menu"><X size={19} /></button></div>
      <div className="nav-label workspace-label">WORKSPACE</div>
      <nav className="nav-list" aria-label="Workspace">{links.map(navItem)}</nav>
      <div className="nav-label account-label">ACCOUNT</div>
      <nav className="nav-list" aria-label="Account">
        {navItem(["Settings", "/settings", Settings])}
        {accountProfile?.app_role === "admin" && navItem(["Account approvals", "/admin/users", ShieldCheck])}
      </nav>
      <div className="sidebar-bottom"><div className="plan-card"><div className="plan-icon"><Sparkles size={16} /></div><div><strong>Need a clearer signal?</strong><span>Review the model guide before taking action.</span></div><a href="#guide" onClick={event => event.preventDefault()}>Open responsible AI guide <span>→</span></a></div>
        <div className="profile-row"><div className="avatar" aria-label={avatar.label}>{avatar.initials}</div><div className="profile-copy"><strong>{displayName}</strong><span>{user?.email}</span></div></div>
      </div>
    </aside>
  </>;
}
