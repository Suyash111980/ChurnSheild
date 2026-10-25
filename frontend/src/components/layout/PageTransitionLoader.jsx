import pinwheel from "../../assets/images/churnshield-transition-pinwheel.png";
import "./PageTransitionLoader.css";

export default function PageTransitionLoader({ state }) {
  if (state === "hidden") return null;
  return (
    <div className={`page-transition-loader is-${state}`} role="status" aria-label="Loading page" aria-live="polite">
      <div className="page-transition-loader-content">
        <span className="page-transition-art-motion" aria-hidden="true">
          <img className="page-transition-art" src={pinwheel} alt="" />
        </span>
        <span className="page-transition-loader-message">Loading...Please Wait !</span>
      </div>
    </div>
  );
}
