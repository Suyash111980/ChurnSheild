import { useMemo } from "react";
import { ChevronLeft, ChevronRight, ShieldAlert } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import LearnerFilters from "../components/learners/LearnerFilters";
import LearnerTable from "../components/learners/LearnerTable";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import LoadingState from "../components/common/LoadingState";
import { useLearners } from "../hooks/useLearners";

const PAGE_SIZE = 20;
const text = (value) => String(value ?? "").toLocaleLowerCase();

function errorMessage(error) {
  const status = Number(error?.message?.match(/\((\d{3})\)/)?.[1]);
  if (status === 401) return "Your session may have expired. Sign in again to access learner records.";
  if (status === 403) return "Your account does not have permission to view learner records.";
  if (status >= 500) return "The learner service is having trouble. Try again in a moment.";
  return "The learner service could not be reached. Check that the API is available and try again.";
}

export default function Learners() {
  const [searchParams, setSearchParams] = useSearchParams();
  const offset = Math.max(0, Number.parseInt(searchParams.get("offset") ?? "0", 10) || 0);
  const search = searchParams.get("q") ?? "";
  const module = searchParams.get("module") ?? "";
  const presentation = searchParams.get("presentation") ?? "";
  const requestedSort = searchParams.get("sort");
  const sort = ["id_student", "code_module", "code_presentation", "highest_education", "region"].includes(requestedSort) ? requestedSort : "id_student";
  const direction = searchParams.get("direction") === "desc" ? "desc" : "asc";
  const { data, loading, error, retry } = useLearners({ limit: PAGE_SIZE, offset });

  const updateParam = (key, value) => setSearchParams((current) => {
    const next = new URLSearchParams(current);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "offset") next.delete("offset");
    return next;
  }, { replace: true });

  const modules = useMemo(() => [...new Set(data.map((item) => item.code_module).filter(Boolean))].sort(), [data]);
  const presentations = useMemo(() => [...new Set(data.map((item) => item.code_presentation).filter(Boolean))].sort(), [data]);
  const hasFilters = Boolean(search || module || presentation);
  const filtered = useMemo(() => {
    const query = text(search).trim();
    return data
      .filter((learner) => {
        const matchesSearch = !query || [learner.student_name, learner.id_student, learner.id, learner.code_module, learner.code_presentation]
          .some((value) => text(value).includes(query));
        return matchesSearch && (!module || learner.code_module === module) && (!presentation || learner.code_presentation === presentation);
      })
      .sort((left, right) => {
        const a = text(left[sort]);
        const b = text(right[sort]);
        return a.localeCompare(b, undefined, { numeric: true }) * (direction === "asc" ? 1 : -1);
      });
  }, [data, direction, module, presentation, search, sort]);

  const clearFilters = () => setSearchParams((current) => {
    const next = new URLSearchParams(current);
    ["q", "module", "presentation", "offset"].forEach((key) => next.delete(key));
    return next;
  }, { replace: true });
  const changeSort = (field) => {
    const nextDirection = sort === field && direction === "asc" ? "desc" : "asc";
    setSearchParams((current) => { const next = new URLSearchParams(current); next.set("sort", field); next.set("direction", nextDirection); return next; }, { replace: true });
  };
  const setPage = (nextOffset) => setSearchParams((current) => { const next = new URLSearchParams(current); if (nextOffset > 0) next.set("offset", String(Math.max(0, nextOffset))); else next.delete("offset"); return next; }, { replace: true });

  const activeFilters = [
    search && { key: "q", label: `Search: ${search}` },
    module && { key: "module", label: `Module: ${module}` },
    presentation && { key: "presentation", label: `Presentation: ${presentation}` },
  ].filter(Boolean);

  return <>
    <PageHeader eyebrow="LEARNER RECORDS" title="Learner Analytics" subtitle="Browse learner-course records returned by your ChurnShield API." />
    <div className="illustrative-banner api-notice"><span className="banner-spark"><ShieldAlert size={16} /></span><span><strong>Backend fields available:</strong> learner identifiers, module, presentation, and demographic fields. Risk scores, risk categories, activity metrics, and display names are not currently returned by this API.</span></div>
    <section className="panel table-panel api-table-panel">
      <div className="api-table-heading"><div><h2>Learner records</h2><p>Search, filter, and sort the current API page. Page navigation uses backend limit and offset.</p></div><span className="api-count">{loading ? "Loading…" : `${filtered.length} shown on this page`}</span></div>
      <LearnerFilters search={search} onSearchChange={(value) => updateParam("q", value)} module={module} onModuleChange={(value) => updateParam("module", value)} modules={modules} presentation={presentation} onPresentationChange={(value) => updateParam("presentation", value)} presentations={presentations} onClear={clearFilters} hasFilters={hasFilters} activeFilters={activeFilters} onRemoveFilter={(key) => updateParam(key, "")} />
      {loading ? <LoadingState rows={6} label="Loading learner records" /> : error ? <ErrorState title="Learner records unavailable" message={errorMessage(error)} onRetry={retry} /> : data.length === 0 ? <EmptyState title="No learner records returned" message="The API returned an empty page. There may be no records, or this page may be beyond the available data." action={offset > 0 ? () => setPage(offset - PAGE_SIZE) : undefined} actionLabel="Previous page" /> : filtered.length === 0 ? <EmptyState title="No matching records" message="No records on this API page match your search and filters." action={clearFilters} /> : <LearnerTable learners={filtered} sort={sort} direction={direction} onSort={changeSort} />}
      {!loading && !error && data.length > 0 && <div className="table-pagination api-pagination"><span>API records <strong>{offset + 1}–{offset + data.length}</strong> · total count is not provided by this endpoint</span><div><button className="page-button" disabled={offset === 0} onClick={() => setPage(offset - PAGE_SIZE)} aria-label="Previous API page"><ChevronLeft size={17} /></button><span className="page-number">Page {Math.floor(offset / PAGE_SIZE) + 1}</span><button className="page-button" disabled={data.length < PAGE_SIZE} onClick={() => setPage(offset + PAGE_SIZE)} aria-label="Next API page"><ChevronRight size={17} /></button></div></div>}
    </section>
    <p className="data-footnote"><span>ⓘ</span> Learner labels use backend display names when available; otherwise the learner ID is shown. Course context and database IDs remain separate.</p>
  </>;
}
