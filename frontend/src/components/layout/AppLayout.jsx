import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  return (
    <div className="app-shell">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="main-column">
        <Topbar onMenu={() => setOpen(true)} />
        <main className="page-content">
          <div className="route-view" key={pathname}>
            <Outlet />
          </div>
        </main>
        <footer className="app-footer">ChurnShield <span>•</span> Authenticated workspace · API-backed learner records</footer>
      </div>
    </div>
  );
}
