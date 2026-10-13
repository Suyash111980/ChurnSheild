import { SearchX } from "lucide-react";

export default function EmptyState({
  title = "No records found",
  message = "There are no records to show right now.",
  action,
  actionLabel = "Clear filters",
}) {
  return (
    <section className="state-card empty-state" aria-live="polite">
      <span className="state-icon"><SearchX size={19} /></span>
      <h2>{title}</h2>
      <p>{message}</p>
      {action && <button className="text-button" type="button" onClick={action}>{actionLabel}</button>}
    </section>
  );
}
