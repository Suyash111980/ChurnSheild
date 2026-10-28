import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Navigate } from "react-router-dom";
import { CheckCircle2, Clock3, RefreshCw, Search, XCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";
import { getAdminRequestDetails, getAdminRequests, reviewAdminRequest } from "../services/adminRequestService";
import { adminRequestCount, adminRequestDisplayName, adminRequestError, adminRequestReviewerName, adminRequestStatusLabel, normalizeAdminRequestPage } from "../utils/adminRequestPresentation";

const PAGE_SIZE = 20;
const TABS = [
  { id: "pending", label: "Pending", Icon: Clock3 },
  { id: "approved", label: "Approved", Icon: CheckCircle2 },
  { id: "rejected", label: "Rejected", Icon: XCircle },
];

function dateTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not recorded" : date.toLocaleString();
}

function userEmail(value) {
  return typeof value === "string" && value.trim() ? value : "Email unavailable";
}

export default function AdminApprovals() {
  const { accountProfile } = useAuth();
  const [status, setStatus] = useState("pending");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState("newest");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [errorRetryable, setErrorRetryable] = useState(false);
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState(null);
  const [detailsForId, setDetailsForId] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");
  const [dialogMode, setDialogMode] = useState("details");
  const [rejectionReason, setRejectionReason] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [working, setWorking] = useState(false);
  usePageTransitionReady(!loading);
  const dialogRef = useRef(null);
  const detailsLoadToken = useRef(0);

  useEffect(() => {
    const timeout = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => { setOffset(0); }, [status, search, dateFrom, dateTo, sort]);

  const requestArgs = useMemo(() => ({
    status, search, dateFrom, dateTo, sort, limit: PAGE_SIZE, offset,
  }), [status, search, dateFrom, dateTo, sort, offset]);

  const loadRequests = useCallback(async () => {
    setLoading(true);
    setError("");
    setErrorRetryable(false);
    setPage(null);
    try {
      const response = await getAdminRequests(requestArgs);
      const normalized = normalizeAdminRequestPage(response);
      if (!normalized) throw new Error("The server returned an invalid Admin request response.");
      setPage(normalized);
    } catch (reason) {
      const failure = adminRequestError(reason);
      setError(failure.message);
      setErrorRetryable(failure.retryable);
    } finally {
      setLoading(false);
    }
  }, [requestArgs]);

  useEffect(() => { loadRequests(); }, [loadRequests]);


  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (selected && !dialog.open) dialog.showModal();
    if (!selected && dialog.open) dialog.close();
  }, [selected]);

  if (accountProfile?.app_role !== "master_admin") return <Navigate to="/dashboard" replace />;

  function clearFilters() {
    setSearchInput("");
    setSearch("");
    setDateFrom("");
    setDateTo("");
    setSort("newest");
    setOffset(0);
  }

  function openDetails(request) {
    const loadToken = ++detailsLoadToken.current;
    setSelected(request);
    setDetails(null);
    setDetailsForId(null);
    setDetailsError("");
    setDetailsLoading(true);
    setDialogMode("details");
    setRejectionReason("");
    setReviewError("");
    getAdminRequestDetails(request.id)
      .then((result) => {
        if (detailsLoadToken.current !== loadToken) return;
        setDetails(result);
        setDetailsForId(request.id);
      })
      .catch((reason) => {
        if (detailsLoadToken.current === loadToken) setDetailsError(reason?.detail || reason?.message || "Workspace and dataset details are unavailable.");
      })
      .finally(() => {
        if (detailsLoadToken.current === loadToken) setDetailsLoading(false);
      });
  }

  async function submitDecision(event) {
    event.preventDefault();
    if (!selected || !["approve", "reject"].includes(dialogMode)) return;
    setWorking(true);
    setReviewError("");
    setError("");
    setNotice("");
    try {
      const response = await reviewAdminRequest(selected.id, dialogMode, rejectionReason.trim());
      const expected = dialogMode === "approve" ? "approved" : "denied";
      if (response?.data?.approval_status !== expected) throw new Error("The server did not confirm the requested decision.");
      const displayName = adminRequestDisplayName(selected);
      setSelected(null);
      setNotice(`${displayName} was ${dialogMode === "approve" ? "approved" : "rejected"}.`);
      await loadRequests();
    } catch (reason) {
      setReviewError(reason?.detail || reason?.message || "The decision could not be saved. Refresh the request before trying again.");
      if (reason?.status === 409 || reason?.status === 404) await loadRequests();
    } finally {
      setWorking(false);
    }
  }

  const requests = page?.data || [];
  const counts = page?.counts;
  const firstResult = page?.count ? offset + 1 : 0;
  const lastResult = page ? Math.min(offset + page.data.length, page.count) : 0;

  return <>
  <section className="admin-requests-page">
    <header className="admin-requests-heading">
      <div><p className="form-eyebrow">PLATFORM ADMINISTRATION</p><h1>Super Admin Dashboard</h1><p>Review admin access requests and track approval decisions.</p></div>
      <button type="button" className="secondary-button" onClick={loadRequests} disabled={loading || working}><RefreshCw size={16}/> Refresh dashboard</button>
    </header>



    {notice && <div className="admin-notice success" role="status">{notice}</div>}
    {error && <div className="admin-notice error" role="alert">{error}{errorRetryable && <button type="button" className="text-button" onClick={loadRequests}>Retry</button>}</div>}

    <section className="admin-request-summary-section" aria-labelledby="admin-request-summary-heading">
    <div className="master-section-heading"><div><h2 id="admin-request-summary-heading">Admin approval requests</h2></div></div>
    <section className="admin-request-summary" aria-label="Admin request totals">
      {TABS.map(({ id, label, Icon }) => <article className={`admin-summary-card ${id}`} key={id}>
        <span className="admin-summary-icon"><Icon size={19}/></span><div><span>{label} Requests</span><strong aria-live="polite">{adminRequestCount(counts, id, { loading, error: Boolean(error) })}</strong></div>
      </article>)}
    </section>
    <p className="admin-count-scope">Counts reflect requests returned by the existing approval service.</p>

    <section className="admin-request-panel panel" aria-label="Admin request management">
      <div className="admin-request-toolbar">
        <label className="admin-search"><span>Search name or email</span><div><Search size={17}/><input type="search" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setOffset(0); }} placeholder="Search by display name or email"/></div></label>
        <label><span>From request date</span><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)}/></label>
        <label><span>To request date</span><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)}/></label>
        <label><span>Sort requests</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Newest request first</option><option value="oldest">Oldest request first</option><option value="reviewed">Most recently reviewed</option></select></label>
        <button type="button" className="admin-clear-filters" onClick={clearFilters} disabled={!searchInput && !dateFrom && !dateTo && sort === "newest"}>Clear filters</button>
      </div>

      <div className="admin-request-tabs" role="tablist" aria-label="Admin request status">
        {TABS.map(({ id, label }) => <button type="button" role="tab" key={id} id={`admin-tab-${id}`} aria-selected={status === id} aria-controls="admin-request-tabpanel" className={status === id ? "active" : ""} onClick={() => setStatus(id)}>{label}<span>{loading ? "…" : counts?.[id] ?? "—"}</span></button>)}
      </div>

      <div id="admin-request-tabpanel" role="tabpanel" aria-labelledby={`admin-tab-${status}`}>
        {loading && <div className="admin-request-loading" role="status">Loading {status} requests…</div>}
        {!loading && !error && requests.length === 0 && <div className="admin-request-empty"><strong>{search || dateFrom || dateTo ? "No matching requests" : `No ${status} requests`}</strong><span>{search || dateFrom || dateTo ? "Clear or adjust the filters to see more requests." : "New requests will appear here when submitted."}</span></div>}
        {!loading && !error && requests.length > 0 && <>
          <div className="admin-request-list">{requests.map((request) => <article className="admin-request-card" key={request.id}>
            <div className="admin-request-identity"><strong>{adminRequestDisplayName(request)}</strong><span>{userEmail(request.email)}</span></div>
            <div className="admin-request-meta"><span className={`admin-status ${request.status}`}><i aria-hidden="true"/>{adminRequestStatusLabel(request.status)}</span><span>Requested {dateTime(request.created_at)}</span>{request.reviewed_at && <span>Reviewed {dateTime(request.reviewed_at)}</span>}</div>
            <div className="admin-request-actions"><button type="button" className="secondary-button" onClick={() => openDetails(request)}>View details</button>{request.status === "pending" && <><button type="button" className="primary-button" onClick={() => { openDetails(request); setDialogMode("approve"); }} disabled={working}>Approve</button><button type="button" className="admin-reject-button" onClick={() => { openDetails(request); setDialogMode("reject"); }} disabled={working}>Reject</button></>}</div>
          </article>)}</div>
          <div className="admin-pagination"><span>Showing {firstResult}–{lastResult} of {page.count} {status} requests</span><div><button type="button" className="secondary-button" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0 || loading}>Previous</button><button type="button" className="secondary-button" onClick={() => setOffset(offset + PAGE_SIZE)} disabled={!page.has_more || loading}>Next</button></div></div>
        </>}
      </div>
    </section>
    </section>

    <section className="admin-activity panel">
      <details open>
        <summary><span><strong>Recent activity</strong><small>Latest persisted request submissions and decisions</small></span><span className="admin-activity-count">{loading ? "…" : page?.activity.length ?? "—"} events</span></summary>
        {loading ? <p className="admin-activity-empty" role="status">Loading activity…</p> : error ? <p className="admin-activity-empty">Activity is unavailable until the request service reconnects.</p> : page?.activity.length === 0 ? <p className="admin-activity-empty">No administrative activity has been recorded yet.</p> : <ol className="admin-activity-list">{(page?.activity || []).map((event, index) => <li key={`${event.action}-${event.created_at}-${index}`}><span className={`admin-activity-marker ${event.action}`} aria-hidden="true"/><div><strong>{event.action === "submitted" ? "Admin request submitted" : event.action === "approved" ? "Admin request approved" : "Admin request rejected"}</strong><p>{event.action === "submitted" ? "Request submitted by" : "Decision by"} <b>{event.actor_display_name || (event.action === "submitted" ? "Applicant" : "Unknown user")}</b> for <b>{event.target_display_name || "Unknown user"}</b>{event.target_email ? ` · ${event.target_email}` : ""}</p>{event.rejection_reason && <p className="admin-activity-reason">Reason: {event.rejection_reason}</p>}<time dateTime={event.created_at}>{dateTime(event.created_at)}</time></div></li>)}</ol>}
      </details>
    </section>

    </section>
    {createPortal(<dialog ref={dialogRef} className="admin-request-dialog" aria-labelledby="admin-dialog-title" onClose={() => setSelected(null)} onCancel={() => setSelected(null)}>
      {selected && <form onSubmit={submitDecision}>
        <div className="admin-dialog-heading"><div><p className="form-eyebrow">ADMIN ACCESS REQUEST</p><h2 id="admin-dialog-title">{dialogMode === "approve" ? "Confirm approval" : dialogMode === "reject" ? "Confirm rejection" : "Request details"}</h2></div><button type="button" className="icon-button" aria-label="Close request details" onClick={() => setSelected(null)}>×</button></div>
        <div className="admin-dialog-user"><strong>{adminRequestDisplayName(selected)}</strong><span>{userEmail(selected.email)}</span></div>
        <dl className="admin-dialog-facts"><div><dt>Request date</dt><dd>{dateTime(selected.created_at)}</dd></div><div><dt>Current status</dt><dd><span className={`admin-status ${selected.status}`}><i aria-hidden="true"/>{adminRequestStatusLabel(selected.status)}</span></dd></div>{selected.reviewed_at && <div><dt>Review date</dt><dd>{dateTime(selected.reviewed_at)}</dd></div>}{(selected.reviewed_at || selected.reviewer_name) && <div><dt>Reviewed by</dt><dd>{adminRequestReviewerName(selected)}{selected.reviewer_email && selected.reviewer_name && selected.reviewer_name.toLowerCase() !== "unknown user" ? ` · ${selected.reviewer_email}` : ""}</dd></div>}{selected.rejection_reason && <div><dt>Rejection reason</dt><dd>{selected.rejection_reason}</dd></div>}
          <div className="admin-dialog-record-group"><dt>Workspace Assigned</dt><dd>{detailsLoading && detailsForId !== selected.id ? "Loading workspace assignments…" : detailsError ? "Workspace information unavailable" : detailsForId !== selected.id ? "Workspace information unavailable" : details?.workspaces?.length ? <ul>{details.workspaces.map((workspace) => <li key={workspace.workspace_id}><strong>{workspace.workspace_name || "Workspace name unavailable"}</strong><span>Workspace ID: {workspace.workspace_id}</span><span>Assigned: {dateTime(workspace.assigned_at)}</span></li>)}</ul> : "No workspace is assigned."}</dd></div>
          <div className="admin-dialog-record-group"><dt>Datasets Uploaded</dt><dd>{detailsLoading && detailsForId !== selected.id ? "Loading uploaded datasets…" : detailsError ? "Dataset information unavailable" : detailsForId !== selected.id ? "Dataset information unavailable" : details?.datasets?.length ? <ul>{details.datasets.map((dataset, index) => <li key={`${dataset.filename}-${dataset.uploaded_at || index}`}><strong>{dataset.filename}</strong><span>Uploaded: {dateTime(dataset.uploaded_at)}</span><span>Rows: {Number.isInteger(dataset.row_count) ? dataset.row_count.toLocaleString() : "Not recorded"}</span></li>)}</ul> : "No datasets uploaded."}</dd></div>
        </dl>
        {dialogMode === "approve" && <p className="admin-dialog-explanation">Approving grants the requested Admin access and provisions an Admin workspace. This decision is recorded in the administrative activity log.</p>}
        {dialogMode === "reject" && <><p className="admin-dialog-explanation">Rejecting denies the requested Admin access. The request history is retained. A reason is optional.</p><label className="admin-rejection-reason">Rejection reason (optional)<textarea maxLength={1000} value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} rows={3}/></label></>}
        {reviewError && <p className="admin-notice error" role="alert">{reviewError}</p>}
        <div className="admin-dialog-actions">{dialogMode === "details" ? <><button type="button" className="secondary-button" onClick={() => setSelected(null)}>Close</button>{selected.status === "pending" && <><button type="button" className="primary-button" onClick={() => setDialogMode("approve")}>Approve request</button><button type="button" className="admin-reject-button" onClick={() => setDialogMode("reject")}>Reject request</button></>}</> : <><button type="button" className="secondary-button" onClick={() => { setDialogMode("details"); setReviewError(""); }} disabled={working}>Cancel</button><button type="submit" className={dialogMode === "approve" ? "primary-button" : "admin-reject-button"} disabled={working}>{working ? "Saving decision…" : dialogMode === "approve" ? "Confirm approval" : "Confirm rejection"}</button></>}</div>
      </form>}
    </dialog>, document.body)}
  </>;
}
