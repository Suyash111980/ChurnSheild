
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Eye,
  EyeOff,
  ShieldCheck,
  ArrowRight,
  LockKeyhole,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../lib/supabase";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const nav = useNavigate();
  const { login } = useAuth();

  const describeAuthError = (authError) => {
    const reason = String(authError?.message || "").toLowerCase();
    if (reason.includes("invalid login credentials") || reason.includes("invalid credentials")) {
      return "Email or password is incorrect. Check your details and try again.";
    }
    if (reason.includes("invalid api key")) {
      return "The Supabase authentication configuration is invalid. Check VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local.";
    }
    if (reason.includes("fetch") || reason.includes("network") || reason.includes("timeout")) {
      return "We couldn’t reach the authentication service. Check your connection and try again.";
    }
    return "We couldn’t sign you in. Check your details and try again.";
  };

  const submit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setMessage("");

    if (!email.trim() || !password) {
      setError("Enter your email and password to continue.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }

    setLoading(true);

    try {
      await login(email.trim(), password);
      nav("/dashboard", { replace: true });
    } catch (err) {
      setError(describeAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async () => {
    if (loading) return;
    setError("");
    setMessage("");

    const normalizedEmail = email.trim().toLowerCase();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setError("Enter your email address first to reset your password.");
      return;
    }

    setLoading(true);

    try {
      const { error: resetError } =
        await supabase.auth.resetPasswordForEmail(normalizedEmail);

      if (resetError) throw resetError;

      setMessage(
        "If an account exists for this email, a password reset link will be sent."
      );
    } catch (err) {
      setError(err.message || "Unable to request a password reset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="auth-brand">
          <div className="brand-icon">
            <ShieldCheck size={22} />
          </div>
          <span>
            Churn<span className="brand-accent">Shield</span>
          </span>
        </div>

        <div className="brand-story">
          <span className="story-kicker">
            <i /> LEARNER SUCCESS, IN FOCUS
          </span>
          <h1>
            Spot the signal.
            <br />
            <em>Keep learners</em>
            <br />
            moving forward.
          </h1>
          <p>
            Understand engagement, identify risk early, and turn insight into
            meaningful action.
          </p>
          <div className="story-proof">
            <div className="proof-avatars">
              <b>J</b>
              <b>M</b>
              <b>A</b>
              <b>+</b>
            </div>
            <span>
              Designed for teams who care
              <br />
              about every learner journey
            </span>
          </div>
        </div>

        <div className="brand-bottom">
          © 2026 ChurnShield <span>•</span> Retention intelligence
        </div>
        <div className="brand-orb orb-one" />
        <div className="brand-orb orb-two" />
      </section>

      <section className="auth-main">
        <div className="auth-mobile-brand">
          <div className="brand-icon">
            <ShieldCheck size={21} />
          </div>
          Churn<span className="brand-accent">Shield</span>
        </div>

        <div className="auth-form-wrap">
          <div className="form-heading">
            <span className="form-icon">
              <LockKeyhole size={18} />
            </span>
            <p className="form-eyebrow">WELCOME BACK</p>
            <h2>Sign in to your workspace</h2>
            <p className="form-subtitle">
              Enter your details to continue to ChurnShield.
            </p>
          </div>

          <div className="demo-note">
            <span className="demo-note-icon">i</span>
            <div>
              <strong>Secure account access</strong>
              <p>Sign in with your ChurnShield account.</p>
            </div>
          </div>

          <form onSubmit={submit} noValidate aria-busy={loading}>
            <label className="field-label" htmlFor="email">
              Email address
            </label>
            <input
              id="email"
              className="text-input"
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              value={email}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "login-error" : undefined}
              onChange={(e) => { setEmail(e.target.value); setError(""); }}
            />

            <div className="password-label">
              <label className="field-label" htmlFor="password">
                Password
              </label>
              <button
                type="button"
                className="text-button"
                onClick={resetPassword}
                disabled={loading}
              >
                Forgot password?
              </button>
            </div>

            <div className="password-wrap">
              <input
                id="password"
                className="text-input"
                type={show ? "text" : "password"}
                placeholder="Enter your password"
                autoComplete="current-password"
                value={password}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "login-error" : undefined}
                onChange={(e) => { setPassword(e.target.value); setError(""); }}
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={show ? "Hide password" : "Show password"}
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>

            {error && (
              <div id="login-error" className="form-error" role="alert">
                {error}
              </div>
            )}

            {message && (
              <div id="login-success" role="status" className="form-success">
                {message}
              </div>
            )}

            <button
              type="submit"
              className="primary-button auth-submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Please wait…
                </>
              ) : (
                <>
                  Sign in <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>

          <p className="auth-switch">
            New to ChurnShield? <Link to="/signup">Create an account</Link>
          </p>

          <div className="auth-legal">
            Secure authentication powered by Supabase.
          </div>
        </div>

        <div className="auth-footer">
          Secure workspace access <span>•</span> ChurnShield
        </div>
      </section>
    </main>
  );
}
