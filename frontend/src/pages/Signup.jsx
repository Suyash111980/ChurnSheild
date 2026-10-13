
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Eye,
  EyeOff,
  ShieldCheck,
  ArrowRight,
  UserPlus,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Signup() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [show, setShow] = useState(false);
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const nav = useNavigate();
  const { signup } = useAuth();

  const update = (key) => (e) =>
    { setError(""); setForm((current) => ({ ...current, [key]: e.target.value })); };

  const submit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setMessage("");

    if (Object.values(form).some((value) => !value.trim())) {
      setError("Complete every field to create your account.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      setError("Enter a valid email address.");
      return;
    }

    if (form.password.length < 8) {
      setError("Use at least 8 characters for your password.");
      return;
    }

    if (form.password !== form.confirm) {
      setError("Your passwords do not match.");
      return;
    }

    if (!terms) {
      setError("Accept the terms to continue.");
      return;
    }

    setLoading(true);

    try {
      const data = await signup({
        name: form.name,
        email: form.email,
        password: form.password,
      });

      if (data.session) {
        nav("/dashboard", { replace: true });
      } else {
        setMessage(
          "Account created. Check your email for a confirmation link before signing in."
        );
      }
    } catch (err) {
      setError(err.message || "Unable to create your account.");
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
            Every learner
            <br />
            has a story.
            <br />
            <em>Help it continue.</em>
          </h1>
          <p>
            Bring engagement signals into view and give your team a clearer
            path to learner success.
          </p>
          <div className="story-proof">
            <div className="proof-avatars">
              <b>J</b>
              <b>M</b>
              <b>A</b>
              <b>+</b>
            </div>
            <span>
              A clearer picture of
              <br />
              every learner journey
            </span>
          </div>
        </div>

        <div className="brand-bottom">
          © 2026 ChurnShield <span>•</span> Retention intelligence
        </div>
        <div className="brand-orb orb-one" />
        <div className="brand-orb orb-two" />
      </section>

      <section className="auth-main signup-main">
        <div className="auth-mobile-brand">
          <div className="brand-icon">
            <ShieldCheck size={21} />
          </div>
          Churn<span className="brand-accent">Shield</span>
        </div>

        <div className="auth-form-wrap">
          <div className="form-heading">
            <span className="form-icon">
              <UserPlus size={18} />
            </span>
            <p className="form-eyebrow">GET STARTED</p>
            <h2>Create your workspace</h2>
            <p className="form-subtitle">
              Create your ChurnShield account.
            </p>
          </div>

          <div className="demo-note">
            <span className="demo-note-icon">i</span>
            <div>
              <strong>Secure account creation</strong>
              <p>Your account is managed by Supabase Auth.</p>
            </div>
          </div>

          <form onSubmit={submit} noValidate aria-busy={loading}>
            <label className="field-label" htmlFor="name">
              Full name
            </label>
            <input
              id="name"
              className="text-input"
              placeholder="Alex Morgan"
              autoComplete="name"
              value={form.name}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "signup-error" : undefined}
              onChange={update("name")}
            />

            <label className="field-label spaced-label" htmlFor="email">
              Email address
            </label>
            <input
              id="email"
              className="text-input"
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              value={form.email}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "signup-error" : undefined}
              onChange={update("email")}
            />

            <label className="field-label spaced-label" htmlFor="password">
              Password
            </label>
            <div className="password-wrap">
              <input
                id="password"
                className="text-input"
                type={show ? "text" : "password"}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                value={form.password}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "signup-error" : undefined}
                onChange={update("password")}
              />
              <button
                type="button"
                className="password-toggle"
                aria-label={show ? "Hide password" : "Show password"}
                title={show ? "Hide password" : "Show password"}
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>

            <label className="field-label spaced-label" htmlFor="confirm">
              Confirm password
            </label>
            <div className="password-wrap">
              <input
                id="confirm"
                className="text-input"
                type={show ? "text" : "password"}
                placeholder="Re-enter your password"
                autoComplete="new-password"
                value={form.confirm}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "signup-error" : undefined}
                onChange={update("confirm")}
              />
            </div>

            <label className="check-row terms-row">
              <input
                type="checkbox"
                checked={terms}
                onChange={(e) => setTerms(e.target.checked)}
              />
              <span className="checkmark" />
              I agree to the terms and understand this is a ChurnShield account.
            </label>

            {error && (
              <div id="signup-error" className="form-error" role="alert">
                {error}
              </div>
            )}

            {message && (
              <div className="form-success" role="status">
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
                  Creating account…
                </>
              ) : (
                <>
                  Create account <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>

          <p className="auth-switch">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>

        <div className="auth-footer">
          Secure workspace access <span>•</span> ChurnShield
        </div>
      </section>
    </main>
  );
}
