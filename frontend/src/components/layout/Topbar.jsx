import { Bell, Menu } from "lucide-react";
import { useLocation } from "react-router-dom";

const titles = { "/dashboard": "Dashboard", "/learners": "Learner Analytics", "/analytics": "Analytics", "/early-warning": "Early Warning Center", "/root-cause": "Root Cause Analysis", "/recommendations": "Recommendations", "/course-insights": "Course Insights", "/reports": "Reports", "/settings": "Settings" };
export default function Topbar({ onMenu }) {
  const { pathname } = useLocation();
  return <header className="topbar"><button className="icon-button mobile-menu" aria-label="Open menu" onClick={onMenu}><Menu size={20}/></button><div className="crumb">ChurnShield <span>›</span> <strong>{titles[pathname] || "Overview"}</strong></div><div className="top-actions"><button className="icon-button notification" aria-label="Notifications"><Bell size={18}/><i/></button><div className="top-avatar">MP</div></div></header>;
}
