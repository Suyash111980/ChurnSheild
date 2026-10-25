import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Eye, EyeOff, KeyRound } from "lucide-react";
import { useNavigate } from "react-router-dom";
import AuthRecoveryLayout from "../components/common/AuthRecoveryLayout";
import AuthLoadingScreen from "../components/common/AuthLoadingScreen";
import { useAuth } from "../context/AuthContext";
import { updateRecoveredPassword } from "../services/authService";
import "./PasswordRecovery.css";

export default function SetNewPassword() {
  const navigate = useNavigate();
  const { user, loading: authLoading, passwordRecovery, clearPasswordRecovery, logout } = useAuth();
  const [recoverySessionValid, setRecoverySessionValid] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [sessionEndFailed, setSessionEndFailed] = useState(false);
  const [endingSession, setEndingSession] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    setRecoverySessionValid(Boolean(passwordRecovery && user));
    setChecking(false);
  }, [authLoading, passwordRecovery, user]);

  async function handlePasswordUpdate(event) {
    event.preventDefault();
    if (loading) return;
    setError("");
    if (!recoverySessionValid) return setError("This password reset link is invalid or has expired. Request a new link to continue.");
    if (!password || !confirm) return setError("Enter and confirm your new password.");
    if (password.length < 8) return setError("Use at least 8 characters for your password.");
    if (password !== confirm) return setError("Your passwords do not match.");

    setLoading(true);
    try {
      await updateRecoveredPassword(password);
      setSuccess(true);
      setPassword("");
      setConfirm("");
      clearPasswordRecovery();
      // Recovery links create a Supabase session. End it after the password update
      // so the user returns to Login and signs in with the new password.
      try { await logout(); } catch { setSessionEndFailed(true); }
    } catch (requestError) {
      setError(requestError?.message?.toLowerCase().includes("expired")
        ? requestError.message
        : "We couldn’t update your password. The reset link may have expired; request a new one and try again.");
    } finally {
      setLoading(false);
    }
  }

  if (checking) return <AuthLoadingScreen title="Validating reset link" description="Checking your secure password recovery session." />;

  if (!recoverySessionValid && !success) {
    return (
      <AuthRecoveryLayout icon={<KeyRound size={18} />} eyebrow="LINK UNAVAILABLE" title="Reset link expired" description="This password reset link is invalid or has expired. Request a new link to securely change your password.">
        <button className="primary-button auth-submit" type="button" onClick={() => navigate("/forgot-password", { replace: true })}>Request a new link <ArrowRight size={17} /></button>
      </AuthRecoveryLayout>
    );
  }

  async function returnToLogin() {
    if (sessionEndFailed) {
      setEndingSession(true);
      try {
        await logout();
        setSessionEndFailed(false);
        navigate("/login", { replace: true });
      } catch {
        setError("Your password was updated, but we couldn’t end the recovery session. Please try again.");
      } finally {
        setEndingSession(false);
      }
      return;
    }
    navigate("/login", { replace: true });
  }

  if (success) {
    return (
      <AuthRecoveryLayout icon={<CheckCircle2 size={18} />} eyebrow="PASSWORD UPDATED" title="You’re all set" description="Your password has been updated. Sign in using your new password.">
        {sessionEndFailed && <div className="form-error" role="alert">Your password was updated. Please end the recovery session before returning to Login.</div>}
        <button className="primary-button auth-submit" type="button" disabled={endingSession} onClick={returnToLogin}>
          {endingSession ? <><span className="spinner" /> Signing out…</> : <>Return to Login <ArrowRight size={17} /></>}
        </button>
      </AuthRecoveryLayout>
    );
  }

  return (
    <AuthRecoveryLayout icon={<KeyRound size={18} />} title="Set New Password" description="Choose a new password for your ChurnShield account.">
      <form className="recovery-form" onSubmit={handlePasswordUpdate} noValidate aria-busy={loading}>
        <label className="field-label" htmlFor="new-password">New Password</label>
        <div className="password-wrap">
          <input id="new-password" className="text-input" type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="At least 8 characters" value={password} onChange={(event) => { setPassword(event.target.value); setError(""); }} aria-invalid={Boolean(error)} aria-describedby={error ? "password-update-error" : "password-requirement"} />
          <button className="password-toggle" type="button" aria-label={showPassword ? "Hide new password" : "Show new password"} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
        </div>
        <p className="recovery-helper" id="password-requirement">Use at least 8 characters.</p>

        <label className="field-label recovery-confirm-label" htmlFor="confirm-new-password">Confirm New Password</label>
        <div className="password-wrap">
          <input id="confirm-new-password" className="text-input" type={showConfirm ? "text" : "password"} autoComplete="new-password" placeholder="Re-enter your password" value={confirm} onChange={(event) => { setConfirm(event.target.value); setError(""); }} aria-invalid={Boolean(error)} aria-describedby={error ? "password-update-error" : undefined} />
          <button className="password-toggle" type="button" aria-label={showConfirm ? "Hide confirmation password" : "Show confirmation password"} onClick={() => setShowConfirm((value) => !value)}>{showConfirm ? <EyeOff size={17} /> : <Eye size={17} />}</button>
        </div>
        {error && <div id="password-update-error" className="form-error" role="alert">{error}</div>}
        <button className="primary-button auth-submit" type="submit" disabled={loading}>
          {loading ? <><span className="spinner" /> Updating password…</> : <>Update Password <ArrowRight size={17} /></>}
        </button>
      </form>
    </AuthRecoveryLayout>
  );
}
