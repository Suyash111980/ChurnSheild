import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import PageTransitionLoader from "./PageTransitionLoader";
import { DatasetProvider } from "../../context/DatasetContext";
import { NavigationTransitionProvider } from "../../context/NavigationTransitionContext";
import { useAuth } from "../../context/AuthContext";

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const { accountProfile } = useAuth();
  const previousPathname = useRef(pathname);
  const generationRef = useRef(0);
  const [transition, setTransition] = useState({ pathname, generation: 0, phase: "hidden" });
  const page = <div className="route-view" key={pathname}><Outlet /></div>;

  useLayoutEffect(() => {
    if (previousPathname.current === pathname) return;
    previousPathname.current = pathname;
    generationRef.current += 1;
    setTransition({ pathname, generation: generationRef.current, phase: "loading" });
  }, [pathname]);

  const reportReady = useCallback((readyPath, generation) => {
    setTransition((current) => current.pathname === readyPath && current.generation === generation && current.phase === "loading"
      ? { ...current, phase: "leaving" }
      : current);
  }, []);

  useEffect(() => {
    if (transition.phase !== "leaving") return undefined;
    const timer = window.setTimeout(() => {
      setTransition((current) => current.generation === transition.generation && current.phase === "leaving"
        ? { ...current, phase: "hidden" }
        : current);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [transition.phase, transition.generation]);

  const contextValue = { generation: transition.generation, reportReady };

  return (
    <NavigationTransitionProvider value={contextValue}>
      <div className="app-shell">
        <Sidebar open={open} onClose={() => setOpen(false)} />
        <div className="main-column">
          <Topbar onMenu={() => setOpen(true)} />
          <main className="page-content">
            <div className={`page-transition-content${transition.phase === "loading" ? " is-pending" : ""}${transition.phase === "leaving" ? " is-revealing" : ""}`} inert={transition.phase === "loading"} aria-hidden={transition.phase === "loading"}>
              {accountProfile?.app_role === "master_admin" ? page : <DatasetProvider>{page}</DatasetProvider>}
            </div>
            <PageTransitionLoader state={transition.phase} />
          </main>
          <footer className="app-footer">ChurnShield <span>•</span> {accountProfile?.app_role === "master_admin" ? "Platform administration" : "Authenticated workspace · API-backed learner records"}</footer>
        </div>
      </div>
    </NavigationTransitionProvider>
  );
}
