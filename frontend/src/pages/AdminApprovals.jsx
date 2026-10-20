
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { apiRequest } from "../services/apiClient";
import { useAuth } from "../context/AuthContext";

export default function AdminApprovals() {
  const { accountProfile } = useAuth();
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState(null);

  const loadPending = useCallback(async () => {
    setError("");
    setLoading(true);

    try {
      const result = await apiRequest("/admin/pending-users");
      setUsers(result.data || []);
      setAccounts(result.accounts || []);
    } catch (err) {
      setError(
        err?.detail ||
          "Unable to load Admin requests. Check your access and try again."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPending();
  }, [loadPending]);

  if (accountProfile?.app_role !== "master_admin") {
    return <Navigate to="/dashboard" replace />;
  }

  async function decide(userId, decision) {
    setWorkingId(userId);
    setError("");
    setNotice("");

    try {
      const result = await apiRequest(`/admin/users/${userId}/approval`, {
        method: "PATCH",
        body: JSON.stringify({ decision }),
      });

      const reviewed = result?.data;
      if (!reviewed) {
        throw new Error("The server returned no approval result.");
      }

      await loadPending();

      if (decision === "approve") {
        const account = (result?.data?.id || userId);
        const refreshed = await apiRequest("/admin/pending-users");
        const updatedAccount = (refreshed.accounts || []).find(
          (item) => item.id === account
        );

        setUsers(refreshed.data || []);
        setAccounts(refreshed.accounts || []);

        if (reviewed.approval_status !== "approved") {
          setError("The server did not confirm that the account is approved.");
        } else if (!updatedAccount?.workspace) {
          setError(
            "The account was approved, but its workspace was not found. Refresh and check the backend workspace provisioning."
          );
        } else {
          setNotice(
            "Admin approved successfully. Their workspace is " +
              updatedAccount.workspace.status +
              "."
          );
        }
      } else {
        setNotice("The Admin request was rejected.");
      }
    } catch (err) {
      setError(
        err?.detail ||
          err?.message ||
          "The request could not be completed. Refresh the list and verify the account status."
      );
    } finally {
      setWorkingId(null);
    }
  }

  const statusLabel = (status) =>
    status === "denied"
      ? "Rejected"
      : status
        ? status[0].toUpperCase() + status.slice(1)
        : "Needs review";

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="form-eyebrow">MASTER ADMIN</p>
          <h1>Admin requests</h1>
        </div>
        <button
          className="text-button"
          onClick={loadPending}
          disabled={loading || workingId !== null}
        >
          Refresh
        </button>
      </header>

      <p className="form-subtitle">
        Approving a request activates the account and creates its own Admin
        workspace.
      </p>

      {error && <div className="form-error" role="alert">{error}</div>}
      {notice && <div className="form-success" role="status">{notice}</div>}

      <h2>Pending requests</h2>

      {loading ? (
        <p role="status">Loading requests…</p>
      ) : users.length === 0 ? (
        <p>No Admin requests are waiting for review.</p>
      ) : (
        <div className="account-approval-list">
          {users.map((user) => (
            <article className="settings-panel" key={user.id}>
              <strong>{user.id}</strong>
              <p className="settings-helper">
                Requested Admin · {user.created_at || "date unavailable"}
              </p>
              <div className="approval-actions">
                <button
                  className="primary-button"
                  disabled={workingId !== null}
                  onClick={() => decide(user.id, "approve")}
                >
                  {workingId === user.id
                    ? "Processing…"
                    : "Approve and create workspace"}
                </button>
                <button
                  className="logout-action"
                  disabled={workingId !== null}
                  onClick={() => decide(user.id, "reject")}
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <h2>Admin account status</h2>

      {loading ? null : accounts.length === 0 ? (
        <p>No Admin requests yet.</p>
      ) : (
        <div className="account-approval-list">
          {accounts.map((account) => (
            <article className="settings-panel" key={account.id}>
              <strong>{account.id}</strong>
              <p>Status: {statusLabel(account.approval_status)}</p>
              <p>
                Workspace:{" "}
                {account.workspace
                  ? `${account.workspace.status} · ${account.workspace.dataset_count} dataset(s) · ${account.workspace.id}`
                  : "Not assigned"}
              </p>
              {account.workspace && (
                <p>
                  Processing:{" "}
                  {Object.entries(
                    account.workspace.processing_status_counts || {}
                  )
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(" · ") || "No datasets"}
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
