import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  BookOpen, ChartNoAxesCombined, FileText, GitBranch, LayoutDashboard,
  LoaderCircle, LogOut, PanelLeftClose, PanelLeftOpen, Settings, ShieldAlert,
  ShieldCheck, Sparkles, UsersRound, X,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { getAvatarDetails } from "../../utils/userAvatar";
import AnimatedLogo from "../common/AnimatedLogo";
import { logoutAndRedirect } from "../../utils/logoutAndRedirect.js";

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
  const { user, logout, accountProfile } = useAuth();
  const avatar = getAvatarDetails(user, accountProfile);
  const displayName = avatar.label !== "User" && avatar.label !== user?.email ? avatar.label : "Account";
  const navigate = useNavigate();
  const sidebarRef = useRef(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");

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
        const focusable = [...(sidebar?.querySelectorAll('a[href], button:not(:disabled)') ?? [])]
          .filter((element) => element.getClientRects().length > 0);
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

  const navItem = ([label, to, Icon]) => (
    <NavLink
      key={to}
      to={to}
      onClick={onClose}
      title={collapsed ? label : undefined}
      aria-label={label}
      data-tooltip={label}
      className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
    ><Icon size={18} aria-hidden="true" /><span>{label}</span></NavLink>
  );

  const leave = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try {
      await logoutAndRedirect(logout, navigate);
    } catch {
      setLogoutError("Could not sign out. Please try again.");
    } finally {
      setLoggingOut(false);
    }
  };

  return <>
    <button className={`drawer-scrim ${open ? "visible" : ""}`} onClick={onClose} tabIndex={open ? 0 : -1} aria-hidden={!open} aria-label="Close navigation drawer" />
    <aside ref={sidebarRef} id="primary-sidebar" className={`sidebar${open ? " drawer-open" : ""}${collapsed ? " collapsed" : ""}`} role={open ? "dialog" : undefined} aria-modal={open || undefined} aria-labelledby={open ? "sidebar-brand" : undefined} aria-label={open ? undefined : "Primary navigation"} aria-hidden={inert || undefined} inert={inert || undefined}>
      <div className="brand">
        <AnimatedLogo variant="sidebar" />
        <span className="brand-name" id="sidebar-brand">Churn<span className="brand-accent">Shield</span></span>
        <button type="button" className="sidebar-collapse-toggle icon-button" onClick={onToggleCollapse} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} aria-expanded={!collapsed} title={collapsed ? "Expand navigation" : "Collapse navigation"}>{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button>
        <button type="button" className="mobile-close icon-button" onClick={onClose} aria-label="Close menu"><X size={19} /></button>
      </div>
      <div className="nav-label workspace-label">WORKSPACE</div>
      <nav className="nav-list" aria-label="Workspace">{links.map(navItem)}</nav>
      {accountProfile?.app_role === "master_admin" && <>
        <div className="nav-label account-label">PLATFORM</div>
        <nav className="nav-list" aria-label="Platform administration">
          {navItem(["Platform Overview", "/master-admin", ShieldCheck])}
          {navItem(["OULAD dataset", "/master-admin/oulad", BookOpen])}
          {navItem(["Admin requests", "/admin/users", ShieldCheck])}
        </nav>
      </>}
      <div className="nav-label account-label">ACCOUNT</div>
      <nav className="nav-list" aria-label="Account">
        {navItem(["Settings", "/settings", Settings])}
        <button type="button" className="nav-link nav-action" onClick={leave} disabled={loggingOut} aria-busy={loggingOut} title={collapsed ? "Log out" : undefined} aria-label={loggingOut ? "Signing out" : "Log out"} data-tooltip="Log out">{loggingOut ? <LoaderCircle className="logout-spinner" size={18} aria-hidden="true" /> : <LogOut size={18} aria-hidden="true" />}<span>{loggingOut ? "Signing out…" : "Log out"}</span></button>
      </nav>
      <div className="sidebar-bottom">
        <div className="plan-card"><div className="plan-icon"><Sparkles size={16} /></div><div><strong>Need a clearer signal?</strong><span>Review the model guide before taking action.</span></div><a href="#guide" onClick={(event) => event.preventDefault()}>Open responsible AI guide <span>→</span></a></div>
        {logoutError && <p className="sidebar-logout-error" role="alert">{logoutError}</p>}
        <div className="profile-row"><div className="avatar" role="img" aria-label={`Signed in as ${avatar.label}`}>{avatar.initials.slice(0, 1)}</div><div className="profile-copy"><strong>{displayName}</strong><span>{user?.email}</span></div><button className="icon-button logout" title={loggingOut ? "Signing out" : "Log out"} aria-label={loggingOut ? "Signing out" : "Log out"} aria-busy={loggingOut} disabled={loggingOut} onClick={leave}>{loggingOut ? <LoaderCircle className="logout-spinner" size={17} /> : <LogOut size={17} />}</button></div>
      </div>
    </aside>
  </>;
}
