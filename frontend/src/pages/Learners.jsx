import { ChevronLeft, ChevronRight, ShieldAlert } from "lucide-react";
import { useLocation, useSearchParams } from "react-router-dom";
import { useDataset } from "../context/DatasetContext";
import PageHeader from "../components/layout/PageHeader";
import LearnerFilters from "../components/learners/LearnerFilters";
import LearnerTable from "../components/learners/LearnerTable";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import LoadingState from "../components/common/LoadingState";
import { useLearners } from "../hooks/useLearners";

const PAGE_SIZE = 20;
function errorMessage(error) {
  const status = Number(error?.status ?? error?.message?.match(/\((\d{3})\)/)?.[1]);
  if (status === 401) return "Your session may have expired. Sign in again to access learner records.";
  if (status === 403) return "Your account does not have permission to view learner records.";
  if (status === 404) return "The selected dataset is unavailable in this workspace.";
  if (status === 409) return "This dataset is still processing. Try again after processing completes.";
  if (status === 422) return error?.detail || "The dataset selection or filters were rejected. Select a dataset and retry.";
  if (status >= 500) return "The learner service is having trouble. Try again in a moment.";
  if (status > 0) return error?.detail || `The learner request failed with HTTP ${status}.`;
  return "The learner service could not be reached. Check that the API is available and try again.";
}

export default function Learners() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const { datasets, datasetId: activeDatasetId } = useDataset();
  const allScope = searchParams.get("scope") === "all";
  const selectedDatasetId = allScope ? "all" : searchParams.get("dataset_id") || activeDatasetId;
  const offset = Math.max(0, Number.parseInt(searchParams.get("offset") ?? "0", 10) || 0);
  const search = searchParams.get("q") ?? "";
  const module = searchParams.get("module") ?? "";
  const presentation = searchParams.get("presentation") ?? "";
  const risk = searchParams.get("risk") ?? "";
  const requestedSort = searchParams.get("sort");
  const sort = ["id_student", "code_module", "code_presentation", "highest_education", "region", "latest_risk_probability", "latest_risk_category"].includes(requestedSort) ? requestedSort : "id_student";
  const direction = searchParams.get("direction") === "desc" ? "desc" : "asc";
  const { data, total, loading, error, retry } = useLearners({
    datasetId: selectedDatasetId,
    limit: PAGE_SIZE,
    offset,
    q: search,
    module,
    presentation,
    risk_category: risk,
    sort,
    direction,
  });

  const updateParam = (key, value) => setSearchParams((current) => {
    const next = new URLSearchParams(current);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "offset") next.delete("offset");
    return next;
  }, ["q", "module", "presentation"].includes(key) ? { replace: true } : undefined);

  const hasFilters = Boolean(search || module || presentation || risk);
  const filtered = data;

  const clearFilters = () => setSearchParams((current) => {
    const next = new URLSearchParams(current);
    ["q", "module", "presentation", "risk", "offset"].forEach((key) => next.delete(key));
    return next;
  });
  const changeSort = (field) => {
    const nextDirection = sort === field && direction === "asc" ? "desc" : "asc";
    setSearchParams((current) => { const next = new URLSearchParams(current); next.set("sort", field); next.set("direction", nextDirection); next.delete("offset"); return next; });
  };
  const setPage = (nextOffset) => setSearchParams((current) => { const next = new URLSearchParams(current); if (nextOffset > 0) next.set("offset", String(Math.max(0, nextOffset))); else next.delete("offset"); return next; });
  const setScope = (value) => setSearchParams((current) => {
    const next = new URLSearchParams(current);
    if (value === "all") { next.set("scope", "all"); next.delete("dataset_id"); }
    else { next.delete("scope"); next.set("dataset_id", value); }
    next.delete("offset");
    return next;
  });

  const activeFilters = [
    search && { key: "q", label: `Search: ${search}` },
    module && { key: "module", label: `Module: ${module}` },
    presentation && { key: "presentation", label: `Presentation: ${presentation}` },
    risk && { key: "risk", label: `Risk: ${risk}` },
  ].filter(Boolean);

  return <>
    <PageHeader eyebrow="LEARNER RECORDS" title="Learner Analytics" subtitle={`Browse ${allScope ? "all authorized datasets" : "the selected dataset"} using saved learner and prediction records.`} />
    <div className="illustrative-banner api-notice"><span className="banner-spark"><ShieldAlert size={16} /></span><span><strong>Verified backend fields:</strong> learner identifiers, course context, available demographics, and persisted latest risk values. Missing predictions remain unavailable rather than being inferred.</span></div>
    <section className="panel table-panel api-table-panel">
      <div className="api-table-heading"><div><h2>Learner records</h2><p>Search, filter, sort, and paginate persisted records across the selected scope.</p></div><span className="api-count">{loading ? "Loading…" : `${filtered.length} shown on this page`}</span></div>
      <label className="learner-dataset-scope">Dataset scope<select aria-label="Learner analytics dataset scope" value={allScope ? "all" : selectedDatasetId} onChange={(event) => setScope(event.target.value)}><option value="all">All Datasets / Overall Class</option>{datasets.map((item) => <option key={item.id} value={item.id}>{item.dataset_name} · {item.status}</option>)}</select></label>
      <LearnerFilters search={search} onSearchChange={(value) => updateParam("q", value)} module={module} onModuleChange={(value) => updateParam("module", value)} presentation={presentation} onPresentationChange={(value) => updateParam("presentation", value)} risk={risk} onRiskChange={(value) => updateParam("risk", value)} onClear={clearFilters} hasFilters={hasFilters} activeFilters={activeFilters} onRemoveFilter={(key) => updateParam(key, "")} />
      {loading ? <LoadingState rows={6} label="Loading learner records" /> : error ? <ErrorState title="Learner records unavailable" message={errorMessage(error)} onRetry={retry} /> : data.length === 0 ? <EmptyState title="No learner records returned" message="There are no persisted learner-course records matching this scope and its filters." action={offset > 0 ? () => setPage(offset - PAGE_SIZE) : undefined} actionLabel="Previous page" /> : <LearnerTable learners={filtered} sort={sort} direction={direction} onSort={changeSort} backTo={`${location.pathname}${location.search}`} />}
      {!loading && !error && data.length > 0 && <div className="table-pagination api-pagination"><span>API records <strong>{offset + 1}–{offset + data.length} of {total}</strong></span><div><button className="page-button" disabled={offset === 0} onClick={() => setPage(offset - PAGE_SIZE)} aria-label="Previous API page"><ChevronLeft size={17} /></button><span className="page-number">Page {Math.floor(offset / PAGE_SIZE) + 1}</span><button className="page-button" disabled={offset + data.length >= total} onClick={() => setPage(offset + PAGE_SIZE)} aria-label="Next API page"><ChevronRight size={17} /></button></div></div>}
    </section>
    <p className="data-footnote"><span>ⓘ</span> Learner labels use backend display names when available; otherwise the learner ID is shown. Course context and database IDs remain separate.</p>
  </>;
}
