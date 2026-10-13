import { AlertTriangle, RefreshCw } from "lucide-react";

export default function ErrorState({
  title = "We couldn’t load this data",
  message = "Check your connection and try again.",
  onRetry,
}) {
  return (
    <section className="state-card error-state" role="alert">
      <span className="state-icon"><AlertTriangle size={19} /></span>
      <h2>{title}</h2>
      <p>{message}</p>
      {onRetry && (
        <button className="secondary-button" type="button" onClick={onRetry}>
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </section>
  );
}
