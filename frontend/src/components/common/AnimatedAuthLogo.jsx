import baseLogo from "../../assets/images/churnshield-auth-base.png";
import arrowLayer from "../../assets/images/churnshield-auth-arrow.png";
import "./AnimatedAuthLogo.css";

export default function AnimatedAuthLogo({
  variant = "hero",
  decorative = false,
  animated = variant === "hero",
  className = "",
}) {
  const classes =
    "auth-logo-stage auth-logo-stage--" +
    variant +
    (animated ? " is-animated" : "") +
    (className ? " " + className : "");

  return (
    <div
      className={classes}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "ChurnShield shield and growth arrow logo"}
      aria-hidden={decorative ? "true" : undefined}
    >
      <img className="auth-logo-base" src={baseLogo} alt="" />
      <img className="auth-logo-arrow-layer" src={arrowLayer} alt="" />
    </div>
  );
}
