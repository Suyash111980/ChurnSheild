import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ShieldAlert } from "lucide-react";
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
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [module, setModule] = useState("");
  const [presentation, setPresentation] = useState("");
  const [sort, setSort] = useState("id_student");
  const [direction, setDirection] = useState("asc");
  const { data, total, loading, error, retry } = useLearners({ limit: PAGE_SIZE, offset });

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

  const clearFilters = () => { setSearch(""); setModule(""); setPresentation(""); };
  const changeSort = (field) => {
    if (sort === field) setDirection((current) => current === "asc" ? "desc" : "asc");
    else { setSort(field); setDirection("asc"); }
  };
  const setPage = (nextOffset) => { clearFilters(); setOffset(Math.max(0, nextOffset)); };

  return <>
    <PageHeader eyebrow="LEARNER RECORDS" title="Learner Analytics" subtitle="Browse learner-course records returned by your ChurnShield API." />
    <div className="illustrative-banner api-notice"><span className="banner-spark"><ShieldAlert size={16} /></span><span><strong>Verified backend fields:</strong> learner identifiers, course context, available demographics, and persisted latest risk values. Missing predictions remain unavailable rather than being inferred.</span></div>
    <section className="panel table-panel api-table-panel">
      <div className="api-table-heading"><div><h2>Learner records</h2><p>Search, filter, and sort the current API page. Page navigation uses backend limit and offset.</p></div><span className="api-count">{loading ? "Loading…" : `${filtered.length} shown on this page`}</span></div>
      <LearnerFilters search={search} onSearchChange={setSearch} module={module} onModuleChange={setModule} modules={modules} presentation={presentation} onPresentationChange={setPresentation} presentations={presentations} onClear={clearFilters} hasFilters={hasFilters} />
      {loading ? <LoadingState rows={6} label="Loading learner records" /> : error ? <ErrorState title="Learner records unavailable" message={errorMessage(error)} onRetry={retry} /> : data.length === 0 ? <EmptyState title="No learner records returned" message="The API returned an empty page. There may be no records, or this page may be beyond the available data." action={offset > 0 ? () => setPage(offset - PAGE_SIZE) : undefined} actionLabel="Previous page" /> : filtered.length === 0 ? <EmptyState title="No matching records" message="No records on this API page match your search and filters." action={clearFilters} /> : <LearnerTable learners={filtered} sort={sort} direction={direction} onSort={changeSort} />}
      {!loading && !error && data.length > 0 && <div className="table-pagination api-pagination"><span>API records <strong>{offset + 1}–{offset + data.length} of {total}</strong></span><div><button className="page-button" disabled={offset === 0} onClick={() => setPage(offset - PAGE_SIZE)} aria-label="Previous API page"><ChevronLeft size={17} /></button><span className="page-number">Page {Math.floor(offset / PAGE_SIZE) + 1}</span><button className="page-button" disabled={offset + data.length >= total} onClick={() => setPage(offset + PAGE_SIZE)} aria-label="Next API page"><ChevronRight size={17} /></button></div></div>}
    </section>
    <p className="data-footnote"><span>ⓘ</span> Learner labels use backend display names when available; otherwise the learner ID is shown. Course context and database IDs remain separate.</p>
  </>;
}
