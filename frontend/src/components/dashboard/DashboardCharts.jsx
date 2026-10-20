import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, AlertTriangle, ArrowRight, BarChart3 } from "lucide-react";
import EmptyState from "../common/EmptyState";
import ErrorState from "../common/ErrorState";

function RecordModuleChart({ learners, loading, error, retry }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const presentation = searchParams.get("chartPresentation") ?? "";
  const presentations = useMemo(() => [...new Set(learners.map((item) => item.code_presentation).filter(Boolean))].sort(), [learners]);
  const filtered = useMemo(() => presentation ? learners.filter((item) => item.code_presentation === presentation) : learners, [learners, presentation]);
  const modules = useMemo(() => {
    const counts = new Map();
    filtered.forEach((item) => {
      if (item.code_module) counts.set(item.code_module, (counts.get(item.code_module) ?? 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [filtered]);
  const total = filtered.length;
  const maximum = Math.max(1, ...modules.map(([, count]) => count));

  return <article className="panel dashboard-chart-card module-chart-card">
    <div className="panel-heading">
      <div><span className="chart-card-icon"><BarChart3 size={16}/></span><h2>Learner records by module</h2><p>Actual records from the current 20-record API page.</p></div>
      <label className="chart-filter-label"><span className="sr-only">Filter chart by presentation</span><select value={presentation} disabled={loading || learners.length === 0} onChange={(event) => setSearchParams((current) => { const next = new URLSearchParams(current); if (event.target.value) next.set("chartPresentation", event.target.value); else next.delete("chartPresentation"); return next; }, { replace: true })}><option value="">All presentations</option>{presentations.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
    </div>
    {loading ? <div className="chart-skeleton" role="status" aria-label="Loading learner chart">{[0,1,2,3,4].map((item) => <i key={item}/>)}</div> : error ? <ErrorState title="Learner chart unavailable" message="The learner API could not be reached, so this chart cannot be calculated." onRetry={retry}/> : !modules.length ? <EmptyState title="No module records available" message="The current API page has no module values to chart."/> : <>
      <p className="module-chart-total">{total.toLocaleString()} records in this view <span>Current API page · not portfolio total</span></p>
      <div className="module-chart-list" role="list" aria-label="Learner record count by module">
        {modules.map(([module, count], index) => {
          const percent = total ? Math.round((count / total) * 100) : 0;
          const to = `/learners?module=${encodeURIComponent(module)}${presentation ? `&presentation=${encodeURIComponent(presentation)}` : ""}`;
          return <Link to={to} className="module-chart-row" role="listitem" key={module} aria-label={`${module}: ${count} records, ${percent}% of records shown. Open filtered learner records`}>
            <span className="module-chart-label">{module}</span>
            <span className="module-chart-track"><i style={{ width: `${(count / maximum) * 100}%`, "--chart-index": index }}/><span className="module-chart-tooltip" role="tooltip">{module} · {count.toLocaleString()} of {total.toLocaleString()} records · {percent}%</span></span>
            <strong>{count.toLocaleString()}</strong><span className="module-chart-percent">{percent}%</span>
          </Link>;
        })}
      </div>
      <p className="chart-footnote">Select a bar to filter the learner directory. Module filters apply to each fetched page because the API has no server-side filter support.</p>
    </>}
  </article>;
}

function UnavailableChart({ icon: Icon, title, description }) {
  return <article className="panel dashboard-chart-card unavailable-chart-card">
    <div className="panel-heading"><div><span className="chart-card-icon unavailable-chart-icon"><Icon size={16}/></span><h2>{title}</h2><p>Live visualization unavailable</p></div></div>
    <div className="chart-unavailable-state"><span>—</span><strong>Data not provided by the current API</strong><p>{description}</p></div>
  </article>;
}

export default function DashboardCharts({ learners, loading, error, retry }) {
  return <section className="dashboard-charts" aria-label="Dashboard charts">
    <RecordModuleChart learners={learners} loading={loading} error={error} retry={retry}/>
    <UnavailableChart icon={AlertTriangle} title="Risk distribution" description="Risk categories and prediction scores are not returned by the current API."/>
    <UnavailableChart icon={Activity} title="Engagement trend" description="The learner endpoint has no activity history or date-based engagement fields."/>
    <div className="dashboard-chart-note"><AlertTriangle size={15}/><span>Charts use backend records only. Risk and engagement charts will become available when the API returns those fields.</span><Link to="/learners">Browse records <ArrowRight size={13}/></Link></div>
  </section>;
}
