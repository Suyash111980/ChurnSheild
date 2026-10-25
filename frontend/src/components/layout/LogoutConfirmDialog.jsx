import { useEffect, useRef } from "react";
import { LogOut, X } from "lucide-react";
import "./LogoutConfirmDialog.css";

export default function LogoutConfirmDialog({ open, pending, error, onCancel, onConfirm }) {
  const cancelRef = useRef(null);
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = document.activeElement;
    cancelRef.current?.focus();
    function handleKeyDown(event) {
      if (event.key === "Escape" && !pending) {
        event.preventDefault();
        onCancel();
      }
      if (event.key === "Tab") {
        if (event.shiftKey && document.activeElement === cancelRef.current) {
          event.preventDefault();
          confirmRef.current?.focus();
        } else if (!event.shiftKey && document.activeElement === confirmRef.current) {
          event.preventDefault();
          cancelRef.current?.focus();
        }
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus?.();
    };
  }, [open, pending, onCancel]);

  if (!open) return null;
  return (
    <div className="logout-dialog-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !pending) onCancel();
    }}>
      <section className="logout-dialog" role="alertdialog" aria-modal="true" aria-labelledby="logout-dialog-title" aria-describedby="logout-dialog-description">
        <button className="logout-dialog-close" type="button" aria-label="Close logout confirmation" onClick={onCancel} disabled={pending}><X size={18} /></button>
        <div className="logout-dialog-icon" aria-hidden="true"><LogOut size={22} /></div>
        <h2 id="logout-dialog-title">Confirm logout</h2>
        <p id="logout-dialog-description">Are you sure you want to log out of your ChurnShield account?</p>
        {error && <p className="logout-dialog-error" role="alert">{error}</p>}
        <div className="logout-dialog-actions">
          <button ref={cancelRef} className="secondary-button logout-dialog-cancel" type="button" onClick={onCancel} disabled={pending}>Cancel</button>
          <button ref={confirmRef} className="logout-dialog-confirm" type="button" onClick={onConfirm} disabled={pending} aria-busy={pending}>
            {pending && <span className="logout-dialog-spinner" aria-hidden="true" />}{pending ? "Logging out…" : "Yes, log out"}
          </button>
        </div>
      </section>
    </div>
  );
}

