import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const percentFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

function useAnimatedValue(value, unit, loading) {
  const initial = value === null || loading ? 0 : value;
  const [displayValue, setDisplayValue] = useState(initial);
  const currentValue = useRef(initial);

  useEffect(() => {
    if (loading || value === null) return undefined;

    const from = currentValue.current;
    const to = value;
    const startAt = performance.now();
    const duration = 850;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;

    if (reducedMotion || from === to) {
      currentValue.current = to;
      setDisplayValue(to);
      return undefined;
    }

    let frameId;
    const animate = (now) => {
      const progress = Math.min((now - startAt) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const nextValue = from + (to - from) * eased;
      currentValue.current = nextValue;
      setDisplayValue(nextValue);
      if (progress < 1) frameId = window.requestAnimationFrame(animate);
    };

    frameId = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frameId);
  }, [loading, value]);

  return unit === "%" ? percentFormat.format(displayValue) : numberFormat.format(displayValue);
}

function KpiCardContent({ label, value, loading, icon: Icon, tone, unit, description }) {
  const animatedValue = useAnimatedValue(value, unit, loading);

  return <>
    {loading ? <span className="kpi-skeleton-icon" aria-hidden="true" /> : <span className={`metric-icon ${tone}`} aria-hidden="true"><Icon size={19} strokeWidth={1.9} /></span>}
    <p className="metric-label">{loading ? <span className="kpi-skeleton-label" aria-hidden="true" /> : label}</p>
    {loading ? <span className="kpi-skeleton-value" aria-hidden="true" /> : <strong className={`kpi-value${value === null ? " kpi-value-unavailable" : ""}`}>{value === null ? "Not available" : `${animatedValue}${unit ?? ""}`}</strong>}
    <span className="kpi-caption">{loading ? "Loading latest data" : description}</span>
  </>;
}

export default function KpiCard(props) {
  const { to, label, index = 0, loading } = props;
  const className = `metric-card dashboard-kpi${to ? " dashboard-kpi-actionable" : ""}`;
  const style = { "--kpi-index": index };

  if (loading) {
    return <article className={className} style={style} aria-label={`Loading ${label}`}>
      <KpiCardContent {...props} />
    </article>;
  }

  if (to) {
    return <Link to={to} className={className} style={style}>
      <KpiCardContent {...props} />
    </Link>;
  }

  return <article className={className} style={style}>
    <KpiCardContent {...props} />
  </article>;
}
