import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import LoginIntro from "../components/common/LoginIntro";

const APPROVAL_POLL_INTERVAL = 30_000;
const APPROVAL_FADE_DURATION = 380;

export default function AccountStatus() {
  const {
    accountProfile,
    profileLoading,
    loading,
    isAuthenticated,
    logout,
    refreshAccountProfile,
  } = useAuth();
  const navigate = useNavigate();
  const [checkError, setCheckError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [approvedLeaving, setApprovedLeaving] = useState(false);
  const checkInFlight = useRef(false);

  const approvalStatus = accountProfile?.approval_status;
  const pending = approvalStatus === "pending";
  const approved = approvalStatus === "approved";
  const denied = ["denied", "rejected", "suspended"].includes(approvalStatus);

  const checkApproval = useCallback(async ({ manual = false } = {}) => {
    if (checkInFlight.current) return;
    checkInFlight.current = true;
    if (manual) setRetrying(true);

    try {
      await refreshAccountProfile({ silent: true });
      setCheckError("");
    } catch {
      setCheckError("We couldn’t check your approval status. Check your connection and retry.");
    } finally {
      checkInFlight.current = false;
      if (manual) setRetrying(false);
    }
  }, [refreshAccountProfile]);

  useEffect(() => {
    if (!pending) return undefined;

    const intervalId = window.setInterval(() => {
      void checkApproval();
    }, APPROVAL_POLL_INTERVAL);

    return () => window.clearInterval(intervalId);
  }, [pending, checkApproval]);

  useEffect(() => {
    if (!approved) {
      setApprovedLeaving(false);
      return undefined;
    }

    setApprovedLeaving(true);
    const timeoutId = window.setTimeout(
      () => navigate("/dashboard", { replace: true }),
      APPROVAL_FADE_DURATION
    );
    return () => window.clearTimeout(timeoutId);
  }, [approved, navigate]);

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
      setSigningOut(false);
    }
  }

  if (loading || (isAuthenticated && profileLoading)) {
    return (
      <LoginIntro
        persistent
        size="signup"
        heading="Checking account approval"
        description="We’re securely checking your account status."
        indicatorLabel="Checking approval status…"
      />
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (approved) {
    return (
      <LoginIntro
        persistent
        leaving={approvedLeaving}
        size="signup"
        heading="Access approved"
        description="Your account is approved. Opening your ChurnShield workspace."
        showIndicator={!approvedLeaving}
      />
    );
  }

  if (denied) {
    const suspended = approvalStatus === "suspended";
    return (
      <main className="not-found" aria-labelledby="account-status-heading">
        <div className="brand-icon" aria-hidden="true"><ShieldCheck size={22} /></div>
        <h1 id="account-status-heading">
          {suspended ? "Account suspended" : "Account access denied"}
        </h1>
        <p>
          {suspended
            ? "Access to this account is suspended. Contact your ChurnShield administrator for help."
            : "An administrator denied access to this account. Contact your ChurnShield administrator if you believe this is a mistake."}
        </p>
        <button className="primary-button" onClick={signOut} disabled={signingOut}>
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </main>
    );
  }

  const statusUnavailable = !pending;
  return (
    <LoginIntro
      persistent
      size="signup"
      heading={statusUnavailable ? "Approval status unavailable" : "Waiting for Admin Approval"}
      description={
        statusUnavailable
          ? "We could not verify your account approval. Retry the status check or sign out and try again."
          : "Your account is awaiting approval from an administrator. This page will update when your access status changes."
      }
      statusMessage={checkError}
      showIndicator={!checkError}
      indicatorLabel={pending ? "Checking for approval updates…" : "Status check needed"}
      onRetry={() => void checkApproval({ manual: true })}
      retrying={retrying}
      onSignOut={signOut}
      signingOut={signingOut}
    />
  );
}
