import { useEffect, useRef, useState } from "react";
import { Bell, LoaderCircle, LogOut, Menu, Moon, Settings, Sun } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import { getAvatarDetails } from "../../utils/userAvatar";
import GlobalSearch from "./GlobalSearch";
import "./InteractiveNavigation.css";

const titles = { "/dashboard": "Dashboard", "/learners": "Learner Analytics", "/analytics": "Analytics", "/early-warning": "Early Warning Center", "/root-cause": "Root Cause Analysis", "/recommendations": "Recommendations", "/course-insights": "Course Insights", "/reports": "Reports", "/settings": "Settings" };

export default function Topbar({ onMenu, menuTriggerRef, mobileNavOpen, onToggleNotifications, notificationOpen, notificationTriggerRef }) {
  const { pathname } = useLocation();
  const { user, accountProfile, logout } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();
  const [profileOpen, setProfileOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const profileRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const restoreFocusOnEscape = useRef(false);
  const navigate = useNavigate();
  const title = pathname.startsWith("/learners/") ? "Learner Profile" : titles[pathname] || "Overview";
  const avatar = getAvatarDetails(user, accountProfile);
  const displayName = avatar.label !== "User" && avatar.label !== user?.email ? avatar.label : "";
  const role = accountProfile?.app_role ?? accountProfile?.role;

  useEffect(() => {
    if (!profileOpen) return undefined;
    const handlePointerDown = (event) => {
      if (!profileRef.current?.contains(event.target)) setProfileOpen(false);
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        restoreFocusOnEscape.current = true;
        setProfileOpen(false);
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        const menuItems = [...(menuRef.current?.querySelectorAll('[role="menuitem"]') ?? [])];
        if (!menuItems.length) return;
        event.preventDefault();
        const active = menuItems.indexOf(document.activeElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? menuItems.length - 1 : event.key === "ArrowDown" ? (active + 1) % menuItems.length : (active <= 0 ? menuItems.length - 1 : active - 1);
        menuItems[next].focus();
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    menuRef.current?.querySelector('[role="menuitem"]')?.focus();
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      if (restoreFocusOnEscape.current) {
        restoreFocusOnEscape.current = false;
        triggerRef.current?.focus();
      }
    };
  }, [profileOpen]);

  const leave = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try {
      await logout();
      setProfileOpen(false);
      navigate("/login", { replace: true });
    } catch {
      setLogoutError("Could not sign out. Please try again.");
    } finally {
      setLoggingOut(false);
    }
  };

  return <header className="topbar">
    <button ref={menuTriggerRef} type="button" className="icon-button mobile-menu" aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"} aria-controls="primary-sidebar" aria-expanded={mobileNavOpen} onClick={onMenu}><Menu size={20}/></button>
    <div className="crumb">ChurnShield <span>›</span> <strong>{title}</strong></div>
    <GlobalSearch isAdmin={accountProfile?.app_role === "admin"}/>
    <div className="top-actions">
      <button type="button" className="icon-button theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`} title={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}>{resolvedTheme === "dark" ? <Sun size={18}/> : <Moon size={18}/>}</button>
      <button ref={notificationTriggerRef} type="button" className="icon-button notification" aria-label="Notifications" aria-haspopup="dialog" aria-expanded={notificationOpen} onClick={onToggleNotifications}><Bell size={18}/></button>
      <div className="profile-menu-wrap" ref={profileRef}>
        <button ref={triggerRef} type="button" className="top-avatar profile-trigger" aria-label={`Open account menu for ${avatar.label}`} aria-haspopup="menu" aria-expanded={profileOpen} onClick={() => { setProfileOpen((value) => !value); setLogoutError(""); }} title={avatar.label}>{avatar.initials}</button>
        {profileOpen && <div className="profile-dropdown" role="menu" aria-label="Account menu" ref={menuRef}>
          <div className="profile-dropdown-identity"><span className="profile-dropdown-avatar">{avatar.initials}</span><div><strong>{displayName || "Account"}</strong>{user?.email && <span>{user.email}</span>}{role && <small>{String(role).replaceAll("_", " ")}</small>}</div></div>
          <div className="profile-dropdown-divider"/>
          <Link role="menuitem" to="/settings" onClick={() => setProfileOpen(false)}><Settings size={16}/> Settings</Link>
          {logoutError && <p className="profile-logout-error" role="alert">{logoutError}</p>}
          <button type="button" role="menuitem" className="profile-logout" onClick={leave} disabled={loggingOut} aria-busy={loggingOut}>{loggingOut ? <LoaderCircle className="logout-spinner" size={16}/> : <LogOut size={16}/>} {loggingOut ? "Signing out…" : "Log out"}</button>
        </div>}
      </div>
    </div>
  </header>;
}
