import { LoaderCircle, LogOut, Menu, Moon, Sun } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCallback, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { getAvatarDetails } from "../../utils/userAvatar";
import { logoutAndRedirect } from "../../utils/logoutAndRedirect.js";
import LogoutConfirmDialog from "./LogoutConfirmDialog";
import { useTheme } from "../../context/ThemeContext";

const titles = { "/dashboard": "Dashboard", "/learners": "Learner Analytics", "/analytics": "Analytics", "/early-warning": "Early Warning Center", "/root-cause": "Root Cause Analysis", "/recommendations": "Recommendations", "/course-insights": "Course Insights", "/reports": "Reports", "/settings": "Settings", "/master-admin": "Platform Overview", "/admin/users": "Admin requests" };

export default function Topbar({ onMenu }) {
  const { pathname } = useLocation();
  const { user, accountProfile, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  const title = pathname.startsWith("/learners/") ? "Learner Profile" : titles[pathname] || "Overview";
  const avatar = getAvatarDetails(user, accountProfile);
  const [logoutDialogOpen, setLogoutDialogOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const navigate = useNavigate();
  const closeLogoutDialog = useCallback(() => {
    if (!loggingOut) {
      setLogoutDialogOpen(false);
      setLogoutError("");
    }
  }, [loggingOut]);

  async function confirmLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try {
      await logoutAndRedirect(logout, navigate);
    } catch {
      setLogoutError("Could not sign out. Please try again.");
      setLoggingOut(false);
    }
  }

  return <>
    <header className="topbar">
      <button className="icon-button mobile-menu" aria-label="Open menu" onClick={onMenu}><Menu size={20} /></button>
      <div className="crumb"><strong>{title}</strong></div>
      <div className="top-actions">
        <button type="button" className="topbar-theme-button" onClick={toggleTheme} aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"} title={isDark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={isDark}>
          {isDark ? <Moon size={17} aria-hidden="true" /> : <Sun size={17} aria-hidden="true" />}
        </button>
        <button type="button" className="topbar-logout-button" onClick={() => { setLogoutError(""); setLogoutDialogOpen(true); }} disabled={loggingOut} aria-label="Log out">
          {loggingOut ? <LoaderCircle className="logout-spinner" size={16} /> : <LogOut size={16} />}
          <span>{loggingOut ? "Logging out…" : "Log out"}</span>
        </button>
        <div className="top-avatar" role="img" aria-label={`Signed in as ${avatar.label}`} title={avatar.label}>{avatar.initials}</div>
      </div>
      {logoutError && !logoutDialogOpen && <span className="topbar-account-error" role="alert">{logoutError}</span>}
    </header>
    <LogoutConfirmDialog open={logoutDialogOpen} pending={loggingOut} error={logoutError} onCancel={closeLogoutDialog} onConfirm={confirmLogout} />
  </>;
}




