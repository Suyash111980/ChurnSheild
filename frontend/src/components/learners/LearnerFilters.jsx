import { Search, X } from "lucide-react";

export default function LearnerFilters({
  search,
  onSearchChange,
  module,
  onModuleChange,
  modules,
  presentation,
  onPresentationChange,
  presentations,
  onClear,
  hasFilters,
}) {
  return (
    <div className="table-toolbar">
      <label className="search-box">
        <Search size={16} aria-hidden="true" />
        <span className="sr-only">Search this page of learner records</span>
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search learner ID or course context on this page…"
        />
      </label>
      <div className="filter-row">
        <label className="filter-select-label">
          <span className="sr-only">Filter by module</span>
          <select value={module} onChange={(event) => onModuleChange(event.target.value)}>
            <option value="">All modules on this page</option>
            {modules.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="filter-select-label">
          <span className="sr-only">Filter by presentation</span>
          <select value={presentation} onChange={(event) => onPresentationChange(event.target.value)}>
            <option value="">All presentations on this page</option>
            {presentations.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        {hasFilters && (
          <button className="secondary-button clear-filter-button" type="button" onClick={onClear}>
            <X size={14} /> Clear
          </button>
        )}
      </div>
    </div>
  );
}
