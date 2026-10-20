import logoImage from "../../assets/Purple Shield Refresh Icon.png";
import shieldMask from "../../assets/churnshield-shield-mask.png";
import arrowMask from "../../assets/churnshield-arrow-mask.png";

/** Uses the original logo image for every visible color pixel; CSS masks stage its reveal. */
export default function AnimatedLogo({ variant = "auth", label = "ChurnShield logo" }) {
  return (
    <span
      className={`animated-logo animated-logo--${variant}`}
      role="img"
      aria-label={label}
      style={{
        "--logo-shield-mask": `url("${shieldMask}")`,
        "--logo-arrow-mask": `url("${arrowMask}")`,
      }}
    >
      <img className="animated-logo__base" src={logoImage} alt="" draggable="false" />
      <img className="animated-logo__shield" src={logoImage} alt="" draggable="false" />
      <img className="animated-logo__arrow" src={logoImage} alt="" draggable="false" />
    </span>
  );
}
