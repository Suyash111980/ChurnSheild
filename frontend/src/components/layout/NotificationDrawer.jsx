import { useEffect, useRef } from "react";
import { Bell, CheckCircle2, X } from "lucide-react";

export default function NotificationDrawer({ open, onClose, triggerRef }) {
  const drawerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = document.activeElement;
    const drawer = drawerRef.current;
    drawer?.querySelector(".notification-close")?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "Tab") {
        const focusable = [...(drawer?.querySelectorAll('a[href], button:not(:disabled)') ?? [])].filter((element) => element.getClientRects().length > 0);
        if (!focusable.length) return;
        if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable.at(-1).focus(); }
        else if (!event.shiftKey && document.activeElement === focusable.at(-1)) { event.preventDefault(); focusable[0].focus(); }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) triggerRef?.current?.focus();
    };
  }, [open, onClose, triggerRef]);

  if (!open) return null;

  return <div className="notification-layer">
    <button type="button" className="notification-backdrop" onClick={onClose} aria-label="Close notifications" tabIndex={-1}/>
    <aside ref={drawerRef} className="notification-drawer" role="dialog" aria-modal="true" aria-labelledby="notification-title">
      <header className="notification-drawer-heading"><div><span className="notification-heading-icon"><Bell size={17}/></span><div><h2 id="notification-title">Notifications</h2><p>Updates for your workspace</p></div></div><span className="notification-status-pill" aria-label="Unread status unavailable because no notification source is connected">Unread unavailable</span><button type="button" className="icon-button notification-close" onClick={onClose} aria-label="Close notifications"><X size={18}/></button></header>
      <div className="notification-empty" role="status"><span><CheckCircle2 size={22}/></span><h3>You’re all caught up</h3><p>No notifications are available. ChurnShield does not have a connected notification event source yet.</p></div>
      <p className="notification-source-note">Notifications will appear here when an application event source is integrated.</p>
    </aside>
  </div>;
}
