import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { apiRequest } from "../services/apiClient";
import { useAuth } from "../context/AuthContext";

const roles = [
  ["retention_manager", "Retention Manager"],
  ["data_analyst", "Analyst"],
  ["admin", "Admin"],
];

export default function AdminApprovals() {
  const { accountProfile } = useAuth();
  const [users, setUsers] = useState([]);
  const [selectedRoles, setSelectedRoles] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState(null);

  const loadPending = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const result = await apiRequest("/admin/pending-users");
      setUsers(result.data || []);
    } catch {
      setError("Unable to load pending accounts. Check your access and try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPending(); }, [loadPending]);

  if (accountProfile?.app_role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  async function decide(userId, approvalStatus) {
    setWorkingId(userId);
    setError("");
    try {
      const body = { approval_status: approvalStatus };
      if (approvalStatus === "approved") {
        body.role = selectedRoles[userId] || "retention_manager";
      }
      await apiRequest(`/admin/users/${userId}/approval`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      await loadPending();
    } catch {
      setError("Unable to update this account. It may already have been reviewed.");
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <section>
      <header className="page-header">
        <div><p className="form-eyebrow">ADMINISTRATION</p><h1>Account approvals</h1></div>
        <button className="text-button" onClick={loadPending} disabled={loading}>Refresh</button>
      </header>
      <p className="form-subtitle">Review new ChurnShield accounts and assign access only after approval.</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      {loading ? <p role="status">Loading pending accounts…</p> : users.length === 0 ? (
        <p>No accounts are waiting for approval.</p>
      ) : (
        <div className="account-approval-list">
          {users.map((user) => (
            <article className="settings-panel" key={user.id}>
              <strong>{user.id}</strong>
              <p className="settings-helper">Created {user.created_at || "date unavailable"}</p>
              <label className="field-label" htmlFor={`role-${user.id}`}>Role on approval</label>
              <select
                id={`role-${user.id}`}
                className="text-input"
                value={selectedRoles[user.id] || "retention_manager"}
                onChange={(event) => setSelectedRoles((current) => ({ ...current, [user.id]: event.target.value }))}
              >
                {roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <div className="approval-actions">
                <button className="primary-button" disabled={workingId === user.id} onClick={() => decide(user.id, "approved")}>Approve</button>
                <button className="logout-action" disabled={workingId === user.id} onClick={() => decide(user.id, "denied")}>Deny</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
