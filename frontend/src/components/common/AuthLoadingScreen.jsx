import shieldLogo from "../../assets/images/churnshield-approval-shield.png";
import "./AuthLoadingScreen.css";

export default function AuthLoadingScreen({ title = "Checking account approval", description = "Verifying your current access status." }) {
  return (
    <main className="auth-loading-screen" role="status" aria-label={`${title}. ${description}`}>
      <section className="auth-loading-card">
        <div className="auth-loading-brand" aria-label="ChurnShield">
          <span>Churn<span>Shield</span></span>
        </div>
        <div className="auth-loading-emblem" aria-hidden="true">
          <span className="auth-loading-ring" />
          <img src={shieldLogo} alt="" />
        </div>
        <h1>{title}</h1>
        <p>{description}</p>
        <div className="auth-loading-indicator" aria-hidden="true"><span /></div>
      </section>
    </main>
  );
}
