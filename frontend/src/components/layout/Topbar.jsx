import { LoaderCircle, LogOut, Menu } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { getAvatarDetails } from "../../utils/userAvatar";

const titles = { "/dashboard": "Dashboard", "/learners": "Learner Analytics", "/analytics": "Analytics", "/early-warning": "Early Warning Center", "/root-cause": "Root Cause Analysis", "/recommendations": "Recommendations", "/course-insights": "Course Insights", "/reports": "Reports", "/settings": "Settings", "/master-admin": "Platform Overview", "/admin/users": "Admin requests" };

export default function Topbar({ onMenu }) {
  const { pathname } = useLocation();
  const { user, accountProfile, logout } = useAuth();
  const title = pathname.startsWith("/learners/") ? "Learner Profile" : titles[pathname] || "Overview";
  const avatar = getAvatarDetails(user, accountProfile);
  const isMasterAdmin = accountProfile?.app_role === "master_admin";
  const isAdminRequestsPage = isMasterAdmin && pathname === "/admin/users";
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const navigate = useNavigate();

  async function leave() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      setLogoutError("Could not sign out. Please try again.");
    } finally {
      setLoggingOut(false);
    }
  }

  return <header className="topbar"><button className="icon-button mobile-menu" aria-label="Open menu" onClick={onMenu}><Menu size={20}/></button><div className="crumb">{isAdminRequestsPage ? <strong>{title}</strong> : <>ChurnShield <span>›</span> <strong>{title}</strong></>}</div><div className={`top-actions${isMasterAdmin ? " master-admin-top-actions" : ""}`}>{isMasterAdmin && <div className="master-admin-account"><div><strong>{avatar.label}</strong><span>{user?.email || ""}</span></div><button type="button" className="master-admin-signout" onClick={leave} disabled={loggingOut} aria-busy={loggingOut}>{loggingOut ? <LoaderCircle className="logout-spinner" size={16}/> : <LogOut size={16}/>}<span>{loggingOut ? "Signing out" : "Log out"}</span></button></div>}<div className="top-avatar" role="img" aria-label={`Signed in as ${avatar.label}`} title={avatar.label}>{avatar.initials}</div></div>{logoutError && <span className="topbar-account-error" role="alert">{logoutError}</span>}</header>;
}
