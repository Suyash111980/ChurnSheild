import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { accountStatusMessage } from "../utils/accountStatusMessage.js";
import AuthLoadingScreen from "../components/common/AuthLoadingScreen";

export default function AccountStatus() {
  const { accountProfile, profileErrorStatus, profileErrorDetail, profileLoading, loading, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  if (loading || (isAuthenticated && profileLoading)) {
    return <AuthLoadingScreen title="Checking account approval" description="Verifying your current access status with ChurnShield." />;
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (accountProfile?.approval_status === "approved") {
    return <Navigate to="/dashboard" replace />;
  }

  const statusMessage = accountStatusMessage({
    approvalStatus: accountProfile?.approval_status,
    profileErrorStatus,
    profileErrorDetail,
  });

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
        {statusMessage.heading}
      </h1>
      <p>{statusMessage.description}</p>
      <button className="primary-button" onClick={signOut}>Sign out</button>
    </main>
  );
}
