import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function AccountStatus() {
  const { accountProfile, profileLoading, loading, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  if (loading || (isAuthenticated && profileLoading)) {
    return <div className="auth-loading" role="status">Checking account approval…</div>;
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (accountProfile?.approval_status === "approved") {
    return <Navigate to="/dashboard" replace />;
  }

  const denied = accountProfile?.approval_status === "denied";
  const pending = accountProfile?.approval_status === "pending";

  async function signOut() {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <main className="not-found" aria-labelledby="account-status-heading">
      <div className="brand-icon"><ShieldCheck size={22} /></div>
      <h1 id="account-status-heading">
        {pending ? "Account awaiting approval" : denied ? "Account access denied" : "Approval status unavailable"}
      </h1>
      <p>
        {pending
          ? "Your account was created successfully. An administrator must approve it before you can use ChurnShield."
          : denied
            ? "An administrator denied access to this account. Contact your ChurnShield administrator if you believe this is a mistake."
            : "We could not verify your account approval. Sign in again or contact your administrator for help."}
      </p>
      <button className="primary-button" onClick={signOut}>Sign out</button>
    </main>
  );
}
