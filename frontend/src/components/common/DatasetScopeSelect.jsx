export default function DatasetScopeSelect({
  value,
  datasets,
  onChange,
  loading = false,
  label = "Dataset scope",
  ariaLabel = "Dataset scope",
  className = "learner-dataset-scope",
  hiddenLabel = false,
}) {
  return (
    <label className={className}>
      <span className={hiddenLabel ? "sr-only" : "dataset-scope-label"}>{label}</span>
      <span className={`dataset-scope-control${loading ? " is-loading" : ""}`} aria-busy={loading}>
        <select aria-label={ariaLabel} value={value || ""} onChange={onChange}>
          <option value="all">All Datasets / Overall Class</option>
          {datasets.map((item) => (
            <option key={item.id} value={item.id}>{item.dataset_name} · {item.status}</option>
          ))}
        </select>
        {loading && <span className="dataset-scope-spinner" role="status" aria-label="Updating dataset scope" />}
      </span>
    </label>
  );
}
