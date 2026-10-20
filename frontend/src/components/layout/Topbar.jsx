import { Bell, Menu } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getAvatarDetails } from "../../utils/userAvatar";

const titles = { "/dashboard": "Dashboard", "/learners": "Learner Analytics", "/analytics": "Analytics", "/early-warning": "Early Warning Center", "/root-cause": "Root Cause Analysis", "/recommendations": "Recommendations", "/course-insights": "Course Insights", "/reports": "Reports", "/settings": "Settings", "/master-admin": "Platform Overview", "/admin/users": "Admin requests" };

export default function Topbar({ onMenu }) {
  const { pathname } = useLocation();
  const { user, accountProfile } = useAuth();
  const title = pathname.startsWith("/learners/") ? "Learner Profile" : titles[pathname] || "Overview";
  const avatar = getAvatarDetails(user, accountProfile);

  return <header className="topbar"><button className="icon-button mobile-menu" aria-label="Open menu" onClick={onMenu}><Menu size={20}/></button><div className="crumb">ChurnShield <span>›</span> <strong>{title}</strong></div><div className="top-actions"><button className="icon-button notification" aria-label="Notifications"><Bell size={18}/><i/></button><div className="top-avatar" role="img" aria-label={`Signed in as ${avatar.label}`} title={avatar.label}>{avatar.initials}</div></div></header>;
}
