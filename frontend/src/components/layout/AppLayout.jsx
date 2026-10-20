import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { DatasetProvider } from "../../context/DatasetContext";
import { useAuth } from "../../context/AuthContext";
import LoginIntro from "../common/LoginIntro";
import NotificationDrawer from "./NotificationDrawer";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const notificationTriggerRef = useRef(null);
  const menuTriggerRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { pathname } = location;
  const { accountProfile } = useAuth();
  const [showLoginIntro, setShowLoginIntro] = useState(
    () => pathname === "/dashboard" && location.state?.showLoginIntro === true
  );
  const [introSize] = useState(
    () => location.state?.introSize === "signup" ? "signup" : "login"
  );
  const consumedSignal = useRef(false);
  const completeLoginIntro = useCallback(() => setShowLoginIntro(false), []);
  const closeMenu = useCallback(() => setOpen(false), []);
  const openMenu = useCallback(() => setOpen(true), []);
  const closeNotifications = useCallback(() => setNotificationOpen(false), []);
  const toggleNotifications = useCallback(() => setNotificationOpen((value) => !value), []);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  useEffect(() => {
    const closeOnDesktop = () => { if (window.innerWidth > 760) setOpen(false); };
    window.addEventListener("resize", closeOnDesktop);
    return () => window.removeEventListener("resize", closeOnDesktop);
  }, []);

  useEffect(() => {
    if (consumedSignal.current || pathname !== "/dashboard" || location.state?.showLoginIntro !== true) return;
    consumedSignal.current = true;
    // Remove the history-state signal immediately so refreshes and later route visits never replay it.
    navigate(
      { pathname: location.pathname, search: location.search, hash: location.hash },
      { replace: true, state: null }
    );
  }, [location, navigate, pathname]);

  return (
    <>
      <div className={`app-shell${collapsed ? " sidebar-is-collapsed" : ""}`} inert={showLoginIntro || notificationOpen ? true : undefined} aria-hidden={showLoginIntro || notificationOpen || undefined}>
        <Sidebar
          open={open}
          onClose={closeMenu}
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((value) => !value)}
          inert={notificationOpen || showLoginIntro}
          menuTriggerRef={menuTriggerRef}
        />
        <div className="main-column" inert={open || notificationOpen || showLoginIntro ? true : undefined}>
          <Topbar
            onMenu={openMenu}
            menuTriggerRef={menuTriggerRef}
            mobileNavOpen={open}
            onToggleNotifications={toggleNotifications}
            notificationOpen={notificationOpen}
            notificationTriggerRef={notificationTriggerRef}
          />
          <main className="page-content">
            <DatasetProvider><div className="route-view" key={pathname}><Outlet /></div></DatasetProvider>
          </main>
          <footer className="app-footer">ChurnShield <span>•</span> {accountProfile?.app_role === "master_admin" ? "Platform administration" : "Authenticated workspace · API-backed learner records"}</footer>
        </div>
      </div>
      {showLoginIntro && <LoginIntro size={introSize} onComplete={completeLoginIntro} />}
      <NotificationDrawer open={notificationOpen} onClose={closeNotifications} triggerRef={notificationTriggerRef} />
    </>
  );
}
