import { useEffect, useState } from "react";
import AnimatedLogo from "./AnimatedLogo";
import "./LoginIntro.css";

/** One-shot visual handoff after successful signup/login; this is not an auth boundary. */
export default function LoginIntro({
  onComplete,
  size = "login",
  persistent = false,
  leaving = false,
  heading = "Welcome to ChurnShield",
  description,
  statusMessage,
  showIndicator = persistent,
  indicatorLabel = "Checking for approval updates…",
  onRetry,
  retrying = false,
  onSignOut,
  signingOut = false,
}) {
  const [timedLeaving, setTimedLeaving] = useState(false);

  useEffect(() => {
    if (persistent) return undefined;

    const reducedMotion = Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
    const leaveTimer = window.setTimeout(() => setTimedLeaving(true), reducedMotion ? 280 : 1970);
    const completeTimer = window.setTimeout(onComplete, reducedMotion ? 560 : 2350);

    return () => {
      window.clearTimeout(leaveTimer);
      window.clearTimeout(completeTimer);
    };
  }, [onComplete, persistent]);

  const isLeaving = leaving || timedLeaving;

  return (
    <div
      className={`login-intro${isLeaving ? " login-intro--leaving" : ""}${persistent ? " login-intro--persistent" : ""}`}
      role={persistent ? undefined : "dialog"}
      aria-modal={persistent ? undefined : "true"}
      aria-live={persistent ? "polite" : undefined}
      aria-labelledby="login-intro-heading"
    >
      <div className="login-intro__content">
        <AnimatedLogo variant={size === "signup" ? "intro-signup" : "intro"} label="ChurnShield" />
        <h1
          id="login-intro-heading"
          className={`login-intro__welcome${size === "signup" ? " login-intro__welcome--signup" : ""}${persistent ? " login-intro__welcome--waiting" : ""}`}
        >
          {heading}
        </h1>
        {description && <p className="login-intro__description">{description}</p>}
        {statusMessage && <p className="login-intro__status-message" role="alert">{statusMessage}</p>}
        {showIndicator && !statusMessage && (
          <div className="login-intro__checking" role="status">
            <span className="login-intro__spinner" aria-hidden="true" />
            {indicatorLabel}
          </div>
        )}
        {(onRetry || onSignOut) && (
          <div className="login-intro__actions">
            {onRetry && (
              <button className="login-intro__action login-intro__action--primary" type="button" onClick={onRetry} disabled={retrying}>
                {retrying ? "Checking…" : "Retry status check"}
              </button>
            )}
            {onSignOut && (
              <button className="login-intro__action" type="button" onClick={onSignOut} disabled={signingOut}>
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
