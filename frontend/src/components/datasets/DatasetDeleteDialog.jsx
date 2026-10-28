import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { AlertCircle, Trash2, X } from "lucide-react";
import "./DatasetDeleteDialog.css";

export default function DatasetDeleteDialog({ dataset, pending, error, onCancel, onConfirm }) {
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);
  const cancelHandlerRef = useRef(onCancel);
  const pendingRef = useRef(pending);
  cancelHandlerRef.current = onCancel;
  pendingRef.current = pending;

  useEffect(() => {
    if (!dataset) return undefined;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cancelRef.current?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape" && !pendingRef.current) {
        event.preventDefault();
        cancelHandlerRef.current?.();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll("button:not(:disabled)");
      if (!focusable?.length) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !dialogRef.current.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialogRef.current.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.();
    };
  }, [Boolean(dataset)]);

  if (!dataset) return null;
  const datasetName = dataset.dataset_name || dataset.filename || "Untitled dataset";

  return createPortal(
    <div
      className="dataset-delete-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !pending) onCancel();
      }}
    >
      <section
        ref={dialogRef}
        className="dataset-delete-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dataset-delete-title"
        aria-describedby="dataset-delete-description"
        tabIndex={-1}
      >
        <button className="dataset-delete-close" type="button" aria-label="Close delete confirmation" onClick={onCancel} disabled={pending}>
          <X size={18} />
        </button>
        <div className="dataset-delete-icon" aria-hidden="true"><Trash2 size={21} /></div>
        <h2 id="dataset-delete-title">Delete dataset?</h2>
        <p className="dataset-delete-intro">You’re about to permanently delete:</p>
        <div className="dataset-delete-name" title={datasetName}>{datasetName}</div>
        <p id="dataset-delete-description" className="dataset-delete-warning">
          This also removes its associated learner records, feature snapshots, predictions, explanations, and recommendations.
        </p>
        {error && <p className="dataset-delete-error" role="alert"><AlertCircle size={16} />{error}</p>}
        <div className="dataset-delete-actions">
          <button className="secondary-button dataset-delete-cancel" type="button" onClick={onCancel} disabled={pending}>Cancel</button>
          <button className="dataset-delete-confirm" type="button" onClick={onConfirm} disabled={pending} aria-busy={pending}>
            {pending && <span className="dataset-delete-spinner" aria-hidden="true" />}
            {pending ? "Deleting…" : "Delete dataset"}
          </button>
        </div>
      </section>
    </div>,
    document.body,
  );
}
