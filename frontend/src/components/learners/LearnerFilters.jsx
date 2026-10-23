import { Search, X } from "lucide-react";

export default function LearnerFilters({
  search,
  onSearchChange,
  module,
  onModuleChange,
  presentation,
  onPresentationChange,
  risk,
  onRiskChange,
  onClear,
  hasFilters,
  activeFilters = [],
  onRemoveFilter,
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
        <label className="filter-select-label"><span className="sr-only">Filter by module</span><input value={module} onChange={(event) => onModuleChange(event.target.value)} placeholder="Module" maxLength={16} /></label>
        <label className="filter-select-label"><span className="sr-only">Filter by presentation</span><input value={presentation} onChange={(event) => onPresentationChange(event.target.value)} placeholder="Presentation" maxLength={16} /></label>
        <label className="filter-select-label"><span className="sr-only">Filter by saved risk category</span><select value={risk} onChange={(event) => onRiskChange(event.target.value)}><option value="">All risk categories</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
        {hasFilters && (
          <button className="secondary-button clear-filter-button" type="button" onClick={onClear}>
            <X size={14} /> Clear
          </button>
        )}
      </div>
      {activeFilters.length > 0 && <div className="active-filter-chips" role="group" aria-label="Active learner filters">
        {activeFilters.map((filter) => <button className="filter-chip" type="button" key={filter.key} onClick={() => onRemoveFilter?.(filter.key)} aria-label={`Remove ${filter.label} filter`}>{filter.label}<X size={12}/></button>)}
      </div>}
    </div>
  );
}
