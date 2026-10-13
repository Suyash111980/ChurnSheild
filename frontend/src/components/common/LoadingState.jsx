export default function LoadingState({ rows = 5, label = "Loading records" }) {
  return (
    <div className="loading-state" role="status" aria-label={label}>
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index} aria-hidden="true">
          <i /><i /><i />
        </div>
      ))}
    </div>
  );
}
