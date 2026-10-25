import { useState } from "react";
import { ArrowRight, Mail } from "lucide-react";
import AuthRecoveryLayout from "../components/common/AuthRecoveryLayout";
import { requestPasswordReset } from "../services/authService";
import "./PasswordRecovery.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleResetRequest(event) {
    event.preventDefault();
    if (loading) return;
    setError("");
    setSuccess(false);

    const address = email.trim();
    if (!address) return setError("Enter your email address to continue.");
    if (!EMAIL_PATTERN.test(address)) return setError("Enter a valid email address.");

    setLoading(true);
    try {
      await requestPasswordReset(address);
      setSuccess(true);
    } catch {
      setError("We couldn’t send the reset link. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthRecoveryLayout
      icon={<Mail size={18} />}
      title="Change Password"
      description="Enter your registered email address and we’ll send you a password reset link."
    >
      <form className="recovery-form" onSubmit={handleResetRequest} noValidate aria-busy={loading}>
        <label className="field-label" htmlFor="recovery-email">Email Address</label>
        <input
          id="recovery-email"
          className="text-input"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
          value={email}
          onChange={(event) => { setEmail(event.target.value); setError(""); setSuccess(false); }}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "recovery-error" : success ? "recovery-success" : undefined}
        />
        {error && <div id="recovery-error" className="form-error" role="alert">{error}</div>}
        {success && <div id="recovery-success" className="form-success" role="status">If an account exists for this email, a password reset link has been sent. Please check your inbox.</div>}
        <button className="primary-button auth-submit" type="submit" disabled={loading}>
          {loading ? <><span className="spinner" /> Sending link…</> : <>Send Reset Link <ArrowRight size={17} /></>}
        </button>
      </form>
    </AuthRecoveryLayout>
  );
}
