import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, LoaderCircle, Search, X } from "lucide-react";
import { getLearners } from "../../services/learnerService";

const sections = [
  ["Dashboard", "/dashboard"], ["Learner Analytics", "/learners"],
  ["Early Warning Center", "/early-warning"], ["Root Cause Analysis", "/root-cause"],
  ["Recommendations", "/recommendations"], ["Course Insights", "/course-insights"],
  ["Reports", "/reports"], ["Settings", "/settings"], ["Analytics", "/analytics"],
];

const searchableText = (value) => String(value ?? "").toLocaleLowerCase();

export default function GlobalSearch({ isAdmin = false }) {
  const [query, setQuery] = useState("");
  const [learnerRecords, setLearnerRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [open, setOpen] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);
  const rootRef = useRef(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const term = query.trim().toLocaleLowerCase();
    if (term.length < 2) {
      setLearnerRecords([]);
      setLoading(false);
      setError("");
      return undefined;
    }

    const controller = new AbortController();
    let current = true;
    setLoading(true);
    setError("");
    const timer = window.setTimeout(() => {
      getLearners({ limit: 100, offset: 0 }, { signal: controller.signal })
        .then((result) => {
          if (!Array.isArray(result?.data)) throw new Error("Unexpected learner search response");
          if (current) setLearnerRecords(result.data.filter((learner) => {
            const identifier = learner?.id;
            if (identifier === null || identifier === undefined || String(identifier).trim() === "") return false;
            return [learner.student_name, learner.id_student, learner.code_module, learner.code_presentation]
              .some((value) => searchableText(value).includes(term));
          }));
        })
        .catch((reason) => {
          if (current && reason.name !== "AbortError") setError("Learner search is unavailable. Check the learner service and try again.");
        })
        .finally(() => { if (current) setLoading(false); });
    }, 300);

    return () => {
      current = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, retryVersion]);

  useEffect(() => {
    const dismiss = (event) => {
      if (event.key === "Escape") setOpen(false);
      if (event.type === "pointerdown" && !rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("keydown", dismiss);
    document.addEventListener("pointerdown", dismiss);
    return () => {
      document.removeEventListener("keydown", dismiss);
      document.removeEventListener("pointerdown", dismiss);
    };
  }, []);

  const navigationResults = useMemo(() => {
    const destinations = isAdmin ? [...sections, ["Account approvals", "/admin/users"]] : sections;
    const term = query.trim().toLocaleLowerCase();
    if (!term) return [];
    return destinations.filter(([label]) => label.toLocaleLowerCase().includes(term))
      .slice(0, 5)
      .map(([label, to]) => ({ kind: "section", label, detail: "Application section", to, key: to }));
  }, [isAdmin, query]);

  const learnerResults = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return learnerRecords.filter((learner) => [learner.student_name, learner.id_student, learner.code_module, learner.code_presentation]
      .some((value) => searchableText(value).includes(term)))
      .slice(0, 6)
      .map((learner) => ({
        kind: "learner",
        label: learner.student_name || `Learner ${learner.id_student ?? learner.id}`,
        detail: [learner.id_student && `ID ${learner.id_student}`, learner.code_module, learner.code_presentation].filter(Boolean).join(" · "),
        to: `/learners/${encodeURIComponent(String(learner.id))}`,
        key: `learner-${learner.id}`,
      }));
  }, [learnerRecords, query]);

  const results = [...navigationResults, ...learnerResults];
  const selectResult = (result) => {
    if (!result) return;
    navigate(result.to);
    setQuery("");
    setOpen(false);
    setActiveIndex(-1);
    inputRef.current?.blur();
  };

  const handleKeyDown = (event) => {
    if (event.key === "ArrowDown" && results.length) {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % results.length);
    } else if (event.key === "ArrowUp" && results.length) {
      event.preventDefault();
      setActiveIndex((current) => current <= 0 ? results.length - 1 : current - 1);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectResult(results[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const term = query.trim();
  const showResults = open && (term.length > 0);

  return <div className="global-search" ref={rootRef}>
    <label className={`global-search-field${open ? " is-open" : ""}`}>
      <Search size={16} aria-hidden="true" />
      <span className="sr-only">Search sections and learner records</span>
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showResults}
        aria-controls="global-search-options"
        aria-activedescendant={activeIndex >= 0 ? `global-search-option-${activeIndex}` : undefined}
        placeholder="Search sections or learner records…"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(event) => { setQuery(event.target.value); setActiveIndex(-1); setOpen(true); }}
        onKeyDown={handleKeyDown}
      />
      {loading && <LoaderCircle size={15} className="global-search-spinner" aria-label="Searching" />}
      {term && <button type="button" className="global-search-clear icon-button" aria-label="Clear search" onClick={() => { setQuery(""); setActiveIndex(-1); inputRef.current?.focus(); }}><X size={14} /></button>}
    </label>
    {showResults && <div className="global-search-results">
      <div id="global-search-options" role="listbox" aria-label="Search results">
        {navigationResults.length > 0 && <div className="global-search-group" role="group" aria-label="Application sections"><span aria-hidden="true">APPLICATION</span>{navigationResults.map((result) => <button key={result.key} id={`global-search-option-${results.indexOf(result)}`} type="button" role="option" aria-selected={results.indexOf(result) === activeIndex} className="global-search-result" onMouseDown={(event) => event.preventDefault()} onClick={() => selectResult(result)}><span className="global-search-result-icon"><ArrowRight size={15} /></span><span><strong>{result.label}</strong><small>{result.detail}</small></span></button>)}</div>}
        {term.length >= 2 && learnerResults.length > 0 && <div className="global-search-group" role="group" aria-label="Learner records"><span aria-hidden="true">LEARNER RECORDS <small>First 100 API records</small></span>{learnerResults.map((result) => <button key={result.key} id={`global-search-option-${results.indexOf(result)}`} type="button" role="option" aria-selected={results.indexOf(result) === activeIndex} className="global-search-result" onMouseDown={(event) => event.preventDefault()} onClick={() => selectResult(result)}><span className="global-search-result-icon learner-result-icon">{result.label.startsWith("Learner ") ? "L" : result.label.charAt(0).toUpperCase()}</span><span><strong>{result.label}</strong><small>{result.detail || "Open learner profile"}</small></span></button>)}</div>}
      </div>
      {term.length < 2 && <p className="global-search-hint">Type at least 2 characters to search learner records.</p>}
      {term.length >= 2 && !loading && !error && !navigationResults.length && !learnerResults.length && <p className="global-search-hint">No matches in the available sections or first 100 learner records.</p>}
      {error && <div className="global-search-error" role="status">{error}<button type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry search</button></div>}
      {term.length >= 2 && <p className="global-search-footnote">Learner results are limited to the first 100 records returned by the API.</p>}
    </div>}
  </div>;
}
