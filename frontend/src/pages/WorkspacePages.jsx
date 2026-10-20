import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { AlertTriangle, ArrowDown, ArrowDownRight, ArrowRight, ArrowUp, ArrowUpDown, ArrowUpRight, CheckCheck, CircleCheck, Clock3, Download, Eye, FileSpreadsheet, FileText, Filter, Lightbulb, ListTodo, Search, Sparkles, UsersRound, X } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import "./CourseInsights.css";
import "./Recommendations.css";

const notice = <div className="illustrative-banner"><span className="banner-spark">ⓘ</span><span><strong>Illustrative demo data</strong> based on the OULAD schema. Values shown are not live predictions or real learner records.</span></div>;
const warnings = [
  ["LNR-7429", "AAA · 2014J", "High", "No activity for 12 days", "12 days ago", "Personal check-in"],
  ["LNR-3158", "DDD · 2014J", "High", "Assessment average is 42%", "8 days ago", "Offer assessment support"],
  ["LNR-8902", "BBB · 2013J", "High", "Two assessments missing", "5 days ago", "Advisor follow-up"],
  ["LNR-6214", "CCC · 2014B", "Medium", "Weekly activity declining", "2 days ago", "Send study plan"],
  ["LNR-4571", "FFF · 2014J", "Medium", "Recent engagement dip", "1 day ago", "Monitor engagement"],
  ["LNR-1963", "GGG · 2013J", "Low", "Engagement recovering", "Today", "Continue monitoring"],
];

function Kpi({ value, label, sub, tone = "purple", Icon }) { return <article className="metric-card compact-kpi"><span className={`metric-icon ${tone}`}>{Icon && <Icon size={18}/>}</span><strong>{value}</strong><span>{label}</span>{sub && <small>{sub}</small>}</article>; }
function Risk({ value }) { return <span className={`risk-badge risk-${value.toLowerCase()}`}><i/>{value}</span>; }
function downloadCsv(filename, rows) { const blob = new Blob([rows.map(row => row.join(",")).join("\n")], { type: "text/csv;charset=utf-8" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url); }

export function EarlyWarning() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const risk = params.get("risk") ?? "";
  const course = params.get("course") ?? "";
  const requestedSort = params.get("sort") || "risk";
  const sort = ["learner", "course", "risk", "signal", "lastActivity", "action"].includes(requestedSort) ? requestedSort : "risk";
  const direction = params.get("direction") === "asc" ? "asc" : "desc";
  const [reviewed, setReviewed] = useState([]);
  const update = (key, value) => setParams((current) => { const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const clearFilters = () => setParams((current) => { const next = new URLSearchParams(current); ["q", "risk", "course"].forEach((key) => next.delete(key)); return next; }, { replace: true });
  const activeFilters = [["q", query && `Search: ${query}`], ["risk", risk && `Risk: ${risk}`], ["course", course && `Course: ${course}`]].filter(([, label]) => label);
  const riskOrder = { Low: 1, Medium: 2, High: 3 };
  const activityOrder = { Today: 0, "1 day ago": 1, "2 days ago": 2, "5 days ago": 5, "8 days ago": 8, "12 days ago": 12 };
  const rows = warnings.filter((row) => (!query || row.join(" ").toLowerCase().includes(query.toLowerCase())) && (!risk || row[2].toLowerCase() === risk.toLowerCase()) && (!course || row[1].startsWith(course)))
    .sort((left, right) => {
      const a = sort === "risk" ? riskOrder[left[2]] : sort === "lastActivity" ? activityOrder[left[4]] : left[{ learner: 0, course: 1, signal: 3, action: 5 }[sort]];
      const b = sort === "risk" ? riskOrder[right[2]] : sort === "lastActivity" ? activityOrder[right[4]] : right[{ learner: 0, course: 1, signal: 3, action: 5 }[sort]];
      const order = typeof a === "number" ? a - b : String(a ?? "").localeCompare(String(b ?? ""), undefined, { numeric: true });
      return order * (direction === "asc" ? 1 : -1);
    });
  const sortHeader = (key, label) => <button type="button" className="sort-button" onClick={() => { const next = new URLSearchParams(params); const nextDirection = sort === key && direction === "desc" ? "asc" : "desc"; next.set("sort", key); next.set("direction", nextDirection); setParams(next, { replace: true }); }} aria-label={`Sort by ${label}${sort === key ? `, currently ${direction}ending` : ""}`}>{label}{sort === key ? (direction === "asc" ? <ArrowUp size={13}/> : <ArrowDown size={13}/>) : <ArrowUpDown size={13}/>}</button>;
  const sortState = (key) => sort === key ? (direction === "asc" ? "ascending" : "descending") : "none";

  return <>
    <PageHeader eyebrow="INTERVENTION WORKSPACE" title="Early Warning Center" subtitle="Prioritize learner outreach using transparent, reviewable warning signals."/>
    <div className="page-heading-actions"><button className="secondary-button" onClick={() => downloadCsv("churnshield-demo-warning-queue.csv", [["Learner ID","Course","Risk","Warning signal","Last activity","Suggested action"], ...rows])}><Download size={15}/> Export queue</button><Link className="primary-button" to="/recommendations"><Sparkles size={15}/> View recommendations</Link></div>
    {notice}
    <section className="metrics-grid warning-kpis">
      <Kpi Icon={AlertTriangle} tone="amber" value="1,248" label="High-risk priority" sub="Needs review"/>
      <Kpi Icon={ArrowDownRight} tone="violet" value="436" label="Inactive 7+ days" sub="35% of priority"/>
      <Kpi Icon={ArrowDownRight} tone="amber" value="518" label="Declining engagement" sub="41% of priority"/>
      <Kpi Icon={FileText} tone="green" value="294" label="Missing assessment" sub="24% of priority"/>
    </section>
    <section className="panel warning-panel">
      <div className="queue-heading"><div><span className="priority-tag"><i/> PRIORITY QUEUE</span><h2>High-risk learner records</h2><p>Review signals before deciding whether an intervention is appropriate.</p></div><div className="review-progress"><span>124 reviewed today</span><i><b/></i><small>61% daily review goal</small></div></div>
      <div className="table-toolbar">
        <label className="search-box"><Search size={16}/><span className="sr-only">Search demo learner or warning signal</span><input value={query} placeholder="Search learner ID or signal..." onChange={(event) => update("q", event.target.value)}/></label>
        <div className="filter-row"><select aria-label="Filter risk level" value={risk} onChange={(event) => update("risk", event.target.value)}>{[["", "All risk levels"],["high","High"],["medium","Medium"],["low","Low"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select><select aria-label="Filter course" value={course} onChange={(event) => update("course", event.target.value)}><option value="">All courses</option>{["AAA","BBB","CCC","DDD","FFF","GGG"].map((item)=><option key={item}>{item}</option>)}</select>{activeFilters.length>0&&<button className="secondary-button" type="button" onClick={clearFilters}><X size={14}/> Clear filters</button>}</div>
      </div>
      {activeFilters.length > 0 && <div className="active-filter-chips" role="group" aria-label="Active warning filters">{activeFilters.map(([key,label])=><button type="button" className="filter-chip" key={key} onClick={()=>update(key,"")} aria-label={`Remove ${label} filter`}>{label}<X size={12}/></button>)}</div>}
      <p className="table-caption">{rows.length} illustrative records shown <span>Sorted by {sort === "lastActivity" ? "last activity" : sort}</span></p>
      <div className="table-scroll"><table className="learner-table"><thead><tr>
        <th aria-sort={sortState("learner")}>{sortHeader("learner","LEARNER ID")}</th><th aria-sort={sortState("course")}>{sortHeader("course","COURSE")}</th><th aria-sort={sortState("risk")}>{sortHeader("risk","RISK LEVEL")}</th><th aria-sort={sortState("signal")}>{sortHeader("signal","WARNING SIGNAL")}</th><th aria-sort={sortState("lastActivity")}>{sortHeader("lastActivity","LAST ACTIVITY")}</th><th aria-sort={sortState("action")}>{sortHeader("action","SUGGESTED ACTION")}</th><th>REVIEW</th>
      </tr></thead><tbody>{rows.map((row)=><tr key={row[0]} tabIndex={0} aria-label={`Illustrative learner ${row[0]}`}><td><strong className="record-link">{row[0]}</strong></td><td>{row[1]}</td><td><Risk value={row[2]}/></td><td>{row[3]}</td><td>{row[4]}</td><td>{row[5]}</td><td><button className="icon-button row-more" aria-label={`Review ${row[0]}`} onClick={()=>setReviewed((current)=>current.includes(row[0])?current:[...current,row[0]])}>{reviewed.includes(row[0])?<span className="reviewed-label">Done</span>:<Eye size={17}/>}</button></td></tr>)}</tbody></table>{rows.length===0&&<div className="table-empty"><strong>No matching records</strong><span>Adjust your search or risk filter.</span></div>}</div>
    </section>
  </>;
}

const rootCauseFeatures = [
  { name: "Days since last activity", value: 0.31, tone: "red", direction: "pushes score higher" },
  { name: "Missing assessments", value: 0.25, tone: "red", direction: "pushes score higher" },
  { name: "7-day VLE clicks", value: 0.18, tone: "red", direction: "pushes score higher" },
  { name: "Previous assessment score", value: 0.12, tone: "red", direction: "pushes score higher" },
  { name: "Early engagement", value: 0.08, tone: "teal", direction: "pushes score lower" },
];

function animatedProgress(elapsed, index) {
  const local = Math.max(0, Math.min(1, (elapsed - index * 105) / 800));
  return 1 - Math.pow(1 - local, 3);
}

function AnimatedFeatureGraph({ animationKey }) {
  const [elapsed, setElapsed] = useState(0);
  const [visibleDirections, setVisibleDirections] = useState({ higher: true, lower: true });

  useEffect(() => {
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    if (reduceMotion) {
      setElapsed(1300);
      return undefined;
    }

    let frame;
    const startedAt = performance.now();
    const tick = (now) => {
      const next = Math.min(now - startedAt, 1300);
      setElapsed(next);
      if (next < 1300) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animationKey]);

  const visibleFeatures = rootCauseFeatures.filter((feature) => visibleDirections[feature.direction === "pushes score higher" ? "higher" : "lower"]);
  return <>
    <div className="feature-legend-controls" aria-label="Toggle feature contribution direction">
      <button type="button" className={`feature-legend-toggle higher${visibleDirections.higher ? " selected" : ""}`} aria-pressed={visibleDirections.higher} onClick={() => setVisibleDirections((current) => ({ ...current, higher: !current.higher }))}><i/> Score increased</button>
      <button type="button" className={`feature-legend-toggle lower${visibleDirections.lower ? " selected" : ""}`} aria-pressed={visibleDirections.lower} onClick={() => setVisibleDirections((current) => ({ ...current, lower: !current.lower }))}><i/> Score decreased</button>
    </div>
    <div className="feature-bars" aria-label="Illustrative feature contributions">
    {visibleFeatures.map((feature) => {
      const index = rootCauseFeatures.indexOf(feature);
      const progress = animatedProgress(elapsed, index);
      const exactValue = (feature.value * progress).toFixed(2);
      const tooltipId = `feature-tip-${index}`;
      return <div className="feature-row" key={feature.name} tabIndex={0} aria-describedby={tooltipId} aria-label={`${feature.name}: ${feature.value.toFixed(2)}, ${feature.direction}`}>
        <span>{feature.name}</span>
        <i className="feature-track"><b className={feature.tone} style={{ width: `${feature.value * progress * 100 / 0.4}%` }}/></i>
        <strong>{exactValue}</strong>
        <span className="feature-tooltip" role="tooltip" id={tooltipId}>{feature.name} · {feature.value.toFixed(2)} · {feature.direction}</span>
      </div>;
    })}
    </div>
    {!visibleFeatures.length && <p className="feature-empty">Both contribution directions are hidden. Enable a legend item to show values.</p>}
  </>;
}

function AnimatedRiskScore({ animationKey, value = 84 }) {
  const [displayValue, setDisplayValue] = useState(0);
  useEffect(() => {
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    if (reduceMotion) {
      setDisplayValue(value);
      return undefined;
    }
    let frame;
    const startedAt = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - startedAt) / 850, 1);
      setDisplayValue(Math.round(value * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animationKey, value]);
  return <strong className="risk-score" aria-label={`Illustrative risk score ${value}`}>{displayValue}</strong>;
}

export function RootCause() {
  const [analyzed, setAnalyzed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [learner, setLearner] = useState("LNR-7429 · AAA · 2014J");
  const [animationKey, setAnimationKey] = useState(1);

  const runIllustrativeAnalysis = () => {
    if (loading) return;
    setLoading(true);
    setAnalyzed(false);
    // This page has no analysis API yet; prepare the existing illustrative snapshot locally.
    window.setTimeout(() => {
      setAnalyzed(true);
      setAnimationKey((key) => key + 1);
      setLoading(false);
    }, 320);
  };

  return <>
    <PageHeader eyebrow="EXPLAINABLE ANALYSIS" title="Root Cause Analysis" subtitle="Review the factors associated with a learner’s illustrative risk score."/>
    {notice}
    <section className="panel analysis-controls">
      <label>Learner record<select value={learner} disabled={loading} onChange={(event) => { setLearner(event.target.value); setAnalyzed(false); }}>
        <option>LNR-7429 · AAA · 2014J</option><option>LNR-3158 · DDD · 2014J</option><option>LNR-6214 · CCC · 2014B</option>
      </select></label>
      <label>Model snapshot<select disabled={loading}><option>Demo model · v1.4</option></select></label>
      <button className="primary-button" onClick={runIllustrativeAnalysis} disabled={loading} aria-busy={loading}>
        {loading ? <><span className="analysis-spinner" aria-hidden="true"/> Preparing demo</> : <><Sparkles size={15}/> Analyze</>}
      </button>
    </section>
    {analyzed && <div className="analysis-result-note" role="status">Illustrative explanation ready for <strong>{learner.split(" · ")[0]}</strong>. This demo snapshot is not a live prediction.</div>}
    <section className="analysis-grid">
      <article className="panel score-card">
        <div className="panel-heading"><h2>Risk summary</h2><Risk value="High"/></div>
        <AnimatedRiskScore key={`score-${animationKey}`} animationKey={animationKey}/>
        <span className="score-caption">Illustrative risk score · not a live prediction</span>
        <div className="score-details">
          <div><span>Course</span><strong>AAA · 2014J</strong></div>
          <div><span>Top signal</span><strong>Recent inactivity</strong></div>
          <div><span>Confidence</span><strong>Requires human review</strong></div>
        </div>
      </article>
      <article className="panel feature-card">
        <div className="panel-heading"><div><h2>Feature importance</h2><p>Illustrative SHAP contributions to this model output</p></div></div>
        <AnimatedFeatureGraph key={`features-${animationKey}`} animationKey={animationKey}/>
        <p className="feature-legend-note">Illustrative contribution values only. No trained model or SHAP API is connected.</p>
      </article>
    </section>
    <section className="panel insight-panel">
      <h2>Model insight</h2>
      <div className="insight-callout"><Sparkles size={16}/>This record’s score is most strongly associated with a long inactivity period and an unsubmitted assessment. Earlier engagement acts as a small counter-signal.</div>
      <h3>Interpret with care</h3><p>Use these signals to guide a conversation, not automate a decision. Context such as accessibility needs or approved breaks may not be represented. Review recent notes before taking action.</p>
    </section>
  </>;
}

const actions = [["Personal advisor check-in","LNR-7429 · 12 days inactive · assessment missing","High","Suggested"],["Offer assessment support","LNR-3158 · Average score 42% · declining activity","High","Reviewed"],["Send study-plan prompt","LNR-4571 · Weekly activity declining","Medium","Action Taken"],["Monitor forum engagement","LNR-6214 · Low participation · active recently","Low","Monitoring"],["Close intervention","LNR-1963 · Activity and scores recovered","Low","Resolved"]];
export function Recommendations() {
  const [status,setStatus]=useState("All statuses"),[selected,setSelected]=useState(null);
  const visible=actions.filter(row=>status==="All statuses"||row[3]===status);
  const metricCards=[["128","Suggested",ListTodo,"purple"],["64","Reviewed",Eye,"blue"],["42","Action Taken",CheckCheck,"teal"],["87","Monitoring",Clock3,"amber"],["156","Resolved",CircleCheck,"green"],["23","No Action Required",X,"slate"]];
  const selectStatus=(next)=>setStatus(current=>current===next?"All statuses":next);
  return <div className="recommendations-page">
    <PageHeader eyebrow="RETENTION WORKSPACE" title="Recommendations" subtitle="Review rule-based actions and track interventions from suggestion to resolution."/>
    <div className="page-heading-actions"><button className="secondary-button recommendation-export" onClick={()=>downloadCsv("churnshield-demo-actions.csv",[["Action","Learner signal","Risk","Status"],...visible])}><Download size={15}/> Export actions</button></div>
    {notice}
    <section className="metrics-grid action-kpis recommendation-kpis" aria-label="Illustrative recommendation workflow counts">
      {metricCards.map(([value,label,Icon,tone])=><button type="button" key={label} className={`action-kpi ${status===label?"is-selected":""}`} onClick={()=>selectStatus(label)} aria-pressed={status===label} aria-label={`${label}: ${value} illustrative actions. ${status===label?"Clear this filter":"Filter action queue by this status"}`}><span className={`action-kpi-icon ${tone}`}><Icon size={18} strokeWidth={1.9}/></span><span className="action-kpi-copy"><strong>{value}</strong><span>{label}</span></span></button>)}
    </section>
    <section className="panel action-queue recommendation-queue">
      <div className="recommendation-queue-heading"><div><h2>Retention action queue</h2><p>Suggestions require review before action.</p></div><div className="queue-controls"><label htmlFor="recommendation-status">Workflow status</label><select id="recommendation-status" aria-label="Filter action status" value={status} onChange={event=>setStatus(event.target.value)}>{["All statuses",...metricCards.map(([,label])=>label)].map(item=><option key={item}>{item}</option>)}</select>{status!=="All statuses"&&<button type="button" className="queue-clear" onClick={()=>setStatus("All statuses")}>Clear filter</button>}</div></div>
      {visible.length>0?<div className="action-list" aria-live="polite">{visible.map(row=><article className="action-row recommendation-action-row" key={row[0]}><i className={`action-edge ${row[2].toLowerCase()}`} aria-hidden="true"/><div className="action-copy"><strong>{row[0]}</strong><span>{row[1]}</span></div><Risk value={row[2]}/><span className={`action-status status-${row[3].toLowerCase().replaceAll(" ","-")}`}>{row[3]}</span><button type="button" className="secondary-button action-review" onClick={()=>setSelected(row)}>Review</button></article>)}</div>:<div className="recommendation-empty" role="status"><span className="recommendation-empty-icon"><ListTodo size={20}/></span><strong>No actions in this status</strong><p>{status} has no matching records in the current illustrative action queue.</p><button type="button" className="secondary-button" onClick={()=>setStatus("All statuses")}>Show all actions</button></div>}
    </section>
    {selected&&<div className="modal-scrim" onClick={()=>setSelected(null)}><section className="learner-modal" role="dialog" aria-modal="true" aria-labelledby="recommendation-dialog-title" onClick={event=>event.stopPropagation()}><button type="button" className="icon-button modal-close" onClick={()=>setSelected(null)} aria-label="Close recommendation details">×</button><span className="modal-demo-label">DEMO RECOMMENDATION</span><h2 id="recommendation-dialog-title">{selected[0]}</h2><p>{selected[1]}</p><p>Suggested actions are illustrative and require a human review before use.</p><button type="button" className="primary-button modal-done" onClick={()=>setSelected(null)}>Close details</button></section></div>}
  </div>;
}

const courseRows=[["AAA","14%","Stable","+3.2%"],["BBB","21%","Watch","−4.8%"],["CCC","18%","Stable","+1.1%"],["DDD","28%","Attention","−9.6%"],["EEE","16%","Watch","−3.4%"],["FFF","23%","Stable","+2.5%"],["GGG","11%","Stable","+1.7%"]];
const coursePresentations=["2013J","2014B","2014J"];
export function CourseInsights() {
  const [presentation,setPresentation]=useState("All presentations");
  const [selectedCourse,setSelectedCourse]=useState(null);
  const hasPresentationSnapshot=presentation==="All presentations";
  const selected=courseRows.find(([code])=>code===selectedCourse);
  const selectCourse=(code)=>setSelectedCourse(current=>current===code?null:code);
  const resetFilters=()=>{setPresentation("All presentations");setSelectedCourse(null);};
  return <div className="course-insights-page">
    <PageHeader eyebrow="COURSE PERFORMANCE" title="Course Insights" subtitle="Compare historical outcomes and engagement patterns across OULAD courses."/>
    <div className="course-controls"><label htmlFor="course-presentation">Presentation</label><select id="course-presentation" value={presentation} onChange={event=>{setPresentation(event.target.value);setSelectedCourse(null);}}><option>All presentations</option>{coursePresentations.map(item=><option key={item}>{item}</option>)}</select>{presentation!=="All presentations"&&<button className="course-reset" type="button" onClick={resetFilters}>Reset filters</button>}<span className="course-filter-note">Presentation-specific course values aren’t available in this illustrative dataset.</span></div>
    {notice}
    <section className="course-insights-grid">
      <article className="panel withdrawal-panel">
        <div className="panel-heading"><div><h2>Historical withdrawal comparison</h2><p>Illustrative share of learner-course records</p></div></div>
        {hasPresentationSnapshot?<div className="course-bar-list" role="list" aria-label="Illustrative withdrawal share by course">{courseRows.map(([course,value,status,trend],index)=><div className={`course-bar-row ${selectedCourse===course?"is-selected":""}`} key={course} role="listitem"><span className="course-bar-code">{course}</span><button type="button" className="course-bar-track" onClick={()=>selectCourse(course)} aria-pressed={selectedCourse===course} aria-label={`${course}: ${value} illustrative withdrawal share. ${status} course health. Select for details.`} title={`${course} · ${value} withdrawal · ${status} · engagement ${trend}`} style={{"--bar-delay":`${index*55}ms`}}><span className="course-bar-fill" style={{"--bar-width":value}}/><span className="course-bar-tooltip" role="tooltip"><strong>{course}</strong><span>Withdrawal: {value}</span><span>Health: {status}</span><span>Engagement change: {trend}</span></span></button><span className="course-bar-value">{value}</span></div>)}</div>:<div className="course-unavailable"><strong>No presentation-specific comparison available</strong><span>The current illustrative course summary has no presentation-level values for {presentation}.</span></div>}
        {selected&&hasPresentationSnapshot&&<div className="course-detail" aria-live="polite"><div><span>Selected course · {selected[0]}</span><strong>{selected[1]} withdrawal share</strong></div><span>{selected[2]} health · engagement change {selected[3]}</span><button type="button" onClick={()=>setSelectedCourse(null)} aria-label="Close selected course details"><X size={15}/></button></div>}
      </article>
      <article className="panel course-health">
        <div className="panel-heading"><div><h2>Course health</h2><p>Illustrative engagement summary</p></div></div>
        {hasPresentationSnapshot?courseRows.map(([course,withdrawal,status,trend],index)=><button type="button" className={`course-health-row ${selectedCourse===course?"is-selected":""}`} key={course} onClick={()=>selectCourse(course)} aria-pressed={selectedCourse===course} style={{"--row-delay":`${index*35}ms`}}><span className="health-code">{course}</span><span className="health-copy"><strong>Module {course}</strong><span>Engagement change <b className={trend.startsWith("−")?"trend-down":"trend-up"}>{trend}</b><i> · {withdrawal} withdrawal</i></span></span><em className={`health-status health-status--${status.toLowerCase()}`}>{status}</em></button>):<div className="course-unavailable"><strong>No presentation-specific course health available</strong><span>Choose “All presentations” to view the illustrative summary currently provided.</span></div>}
        {selected&&hasPresentationSnapshot&&<div className="health-selection" aria-live="polite"><strong>Module {selected[0]}</strong><span>{selected[2]} · engagement change {selected[3]} · illustrative withdrawal share {selected[1]}</span></div>}
      </article>
      <article className="panel weekly-panel">
        <div className="panel-heading"><div><h2>Weekly course engagement</h2><p>Weekly activity by course</p></div></div>
        <div className="weekly-unavailable"><span className="weekly-empty-icon" aria-hidden="true">↗</span><div><strong>Weekly activity data unavailable</strong><p>The current Course Insights data includes engagement change summaries, but no weekly activity values. This chart will appear when the API provides a time series.</p></div></div>
      </article>
    </section>
  </div>;
}

const reportTypes=[["Learner Summary","Portfolio overview of risk tiers, engagement, and assessment status.",UsersRound], ["Risk Analysis","Explainable risk signals by course, presentation, and learner group.",FileSpreadsheet], ["Retention Recommendations","Actions, supporting indicators, owners, and intervention statuses.",Lightbulb]];
export function Reports() { return <><PageHeader eyebrow="REPORTING CENTER" title="Reports" subtitle="Create review-ready exports from filtered illustrative OULAD data."/>{notice}<section className="panel report-filters"><label>Presentation<select><option>All presentations</option><option>2014J</option></select></label><label>Course<select><option>All courses</option>{["AAA","BBB","CCC","DDD"].map(x=><option key={x}>{x}</option>)}</select></label><label>Risk level<select><option>All risk levels</option><option>High</option><option>Medium</option><option>Low</option></select></label><button className="secondary-button"><Filter size={14}/> Apply filters</button></section><section className="report-grid">{reportTypes.map(([title,desc,Icon])=><article className="panel report-card" key={title}><span className="report-icon"><Icon size={20}/></span><h2>{title}</h2><p>{desc}</p><div className="report-meta"><span>◷ Generated on request</span><em>Filtered</em></div><div className="report-buttons"><button className="primary-button" onClick={()=>downloadCsv(`${title.toLowerCase().replaceAll(" ","-")}-demo.csv`,[["Report","Preview"],[title,"Illustrative data only"]])}><Download size={14}/> Export CSV</button><button className="secondary-button" onClick={()=>downloadCsv(`${title.toLowerCase().replaceAll(" ","-")}-demo.csv`,[["Report","Preview"],[title,"Illustrative data only"]])}><Download size={14}/> Excel</button></div></article>)}</section></> }
