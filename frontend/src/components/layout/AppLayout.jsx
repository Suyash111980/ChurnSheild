import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { DatasetProvider } from "../../context/DatasetContext";
import { useAuth } from "../../context/AuthContext";

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const { accountProfile } = useAuth();

  return (
    <div className="app-shell">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="main-column">
        <Topbar onMenu={() => setOpen(true)} />
        <main className="page-content">
          <DatasetProvider><div className="route-view" key={pathname}><Outlet /></div></DatasetProvider>
        </main>
        <footer className="app-footer">ChurnShield <span>•</span> {accountProfile?.app_role === "master_admin" ? "Platform administration" : "Authenticated workspace · API-backed learner records"}</footer>
      </div>
    </div>
  );
}
