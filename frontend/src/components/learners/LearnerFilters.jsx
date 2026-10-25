import { Search, X } from "lucide-react";

export default function LearnerFilters({
  search,
  onSearchChange,
  risk,
  onRiskChange,
  onClear,
  hasFilters,
}) {
  return (
    <div className="table-toolbar">
      <label className="search-box">
        <Search size={16} aria-hidden="true" />
        <span className="sr-only">Search learner ID or course context across the selected scope</span>
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search learner ID or course context across this scope…"
        />
      </label>
      <div className="filter-row">
        <label className="filter-select-label"><span className="sr-only">Filter by saved risk category</span><select value={risk} onChange={(event) => onRiskChange(event.target.value)}><option value="">All risk categories</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
        {hasFilters && (
          <button className="secondary-button clear-filter-button" type="button" onClick={onClear}>
            <X size={14} /> Clear
          </button>
        )}
      </div>
    </div>
  );
}
