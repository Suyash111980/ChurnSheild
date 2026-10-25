import { Link } from "react-router-dom";
import AnimatedAuthLogo from "./AnimatedAuthLogo";

export default function AuthRecoveryLayout({ icon, eyebrow = "ACCOUNT RECOVERY", title, description, children }) {
  return (
    <main className="auth-page auth-recovery-page">
      <section className="auth-brand-panel">
        <div className="auth-brand auth-brand-animated">
          <AnimatedAuthLogo variant="brand" decorative animated />
          <span className="auth-brand-name">Churn<span className="brand-accent">Shield</span></span>
        </div>
        <div className="brand-story">
          <span className="story-kicker"><i /> SECURE ACCOUNT ACCESS</span>
          <h1>Get back to<br /><em>your workspace.</em></h1>
          <p>Recover access to your ChurnShield learner retention workspace with a secure, verified password reset.</p>
        </div>
        <div className="brand-bottom">© 2026 ChurnShield <span>•</span> Retention intelligence</div>
        <div className="brand-orb orb-one" />
        <div className="brand-orb orb-two" />
      </section>

      <section className="auth-main">
        <div className="auth-mobile-brand auth-brand-animated">
          <AnimatedAuthLogo variant="brand" decorative animated />
          <span className="auth-brand-name">Churn<span className="brand-accent">Shield</span></span>
        </div>
        <div className="auth-form-wrap recovery-form-wrap">
          <div className="form-heading recovery-form-heading">
            <span className="form-icon">{icon}</span>
            <p className="form-eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
            <p className="form-subtitle">{description}</p>
          </div>
          {children}
          <p className="auth-switch"><Link to="/login">Back to Login</Link></p>
          <div className="auth-legal">Secure authentication powered by Supabase.</div>
        </div>
        <div className="auth-footer">Secure workspace access <span>•</span> ChurnShield</div>
      </section>
    </main>
  );
}
