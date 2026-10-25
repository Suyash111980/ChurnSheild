import { useState } from "react";

const RISK_COLORS = { high: "#e7465b", medium: "#6948f5", low: "#11b7a2" };
const RISK_LABELS = { high: "High Risk", medium: "Medium Risk", low: "Low Risk" };

function describeArc(startAngle, sweepAngle, radius) {
  const point = (angle) => {
    const radians = ((angle - 90) * Math.PI) / 180;
    return { x: 110 + radius * Math.cos(radians), y: 110 + radius * Math.sin(radians) };
  };
  const start = point(startAngle);
  if (sweepAngle >= 359.999) {
    const middle = point(startAngle + 180);
    return `M ${start.x} ${start.y} A ${radius} ${radius} 0 1 1 ${middle.x} ${middle.y} A ${radius} ${radius} 0 1 1 ${start.x} ${start.y}`;
  }
  const end = point(startAngle + sweepAngle);
  const largeArc = sweepAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

export default function RiskDistributionChart({ distribution }) {
  const [activeRisk, setActiveRisk] = useState(null);
  const hasCounts = distribution && ["high", "medium", "low"].every((key) =>
    typeof distribution[key] === "number" && Number.isFinite(distribution[key]) && distribution[key] >= 0
  );
  const risks = hasCounts ? ["high", "medium", "low"].map((key) => ({
    key, label: RISK_LABELS[key], value: distribution[key], color: RISK_COLORS[key],
  })) : [];
  const total = risks.reduce((sum, item) => sum + item.value, 0);
  let offset = 0;
  const segments = risks.map((risk, index) => {
    const percentage = total > 0 ? (risk.value / total) * 100 : 0;
    const segment = { ...risk, percentage, offset, delay: `${index * 110}ms` };
    offset += percentage;
    return segment;
  });
  const selected = segments.find((item) => item.key === activeRisk);

  return (
    <section className="panel risk-distribution-panel" aria-labelledby="risk-distribution-title">
      <div className="panel-heading">
        <div><h2 id="risk-distribution-title">Learner risk distribution</h2><p>Saved predictions by risk category</p></div>
        <span className="risk-chart-total-label">{hasCounts ? `${total.toLocaleString()} saved predictions` : "Risk data unavailable"}</span>
      </div>
      {!hasCounts ? (
        <div className="risk-chart-empty" role="status">Risk distribution is unavailable for this dataset.</div>
      ) : total === 0 ? (
        <div className="risk-chart-empty" role="status">No saved risk predictions are available for this dataset yet.</div>
      ) : (
        <div className="risk-distribution-content">
          <div className="risk-chart-visual">
            {selected && <div className="risk-chart-tooltip" role="status"><strong>{selected.label}</strong><span>{selected.value.toLocaleString()} learners · {selected.percentage.toFixed(1)}%</span></div>}
            <svg className="risk-donut" viewBox="0 0 220 220" role="group" aria-label="Interactive learner risk distribution donut chart">
              <circle className="risk-donut-track" cx="110" cy="110" r="77" />
              {segments.filter((segment) => segment.value > 0).map((segment) => {
                const isDimmed = activeRisk && activeRisk !== segment.key;
                return (
                  <path
                    key={segment.key}
                    className={`risk-donut-segment ${isDimmed ? "is-dimmed" : ""} ${activeRisk === segment.key ? "is-active" : ""}`}
                    d={describeArc(segment.offset * 3.6, segment.percentage * 3.6, 77)}
                    pathLength="100" fill="none" stroke={segment.color} strokeWidth="17"
                    strokeDasharray="100 100" strokeDashoffset="0"
                    style={{ "--segment-delay": segment.delay }}
                    tabIndex="0" role="button"
                    aria-label={`${segment.label}: ${segment.value.toLocaleString()} learners, ${segment.percentage.toFixed(1)} percent`}
                    aria-pressed={activeRisk === segment.key}
                    onMouseEnter={() => setActiveRisk(segment.key)}
                    onMouseLeave={() => setActiveRisk((current) => current === segment.key ? null : current)}
                    onFocus={() => setActiveRisk(segment.key)}
                    onBlur={() => setActiveRisk((current) => current === segment.key ? null : current)}
                    onClick={() => setActiveRisk((current) => current === segment.key ? null : segment.key)}
                    onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setActiveRisk((current) => current === segment.key ? null : segment.key); } }}
                  ><title>{`${segment.label}: ${segment.value.toLocaleString()} learners (${segment.percentage.toFixed(1)}%)`}</title></path>
                );
              })}
            </svg>
            <div className="risk-donut-center" aria-hidden="true"><strong>{total.toLocaleString()}</strong><span>learners</span></div>
          </div>
          <div className="risk-distribution-legend" aria-label="Risk categories">
            {segments.map((segment) => (
              <button key={segment.key} type="button" className={`risk-legend-item ${activeRisk === segment.key ? "is-active" : ""} ${activeRisk && activeRisk !== segment.key ? "is-dimmed" : ""}`}
                onMouseEnter={() => setActiveRisk(segment.key)} onMouseLeave={() => setActiveRisk((current) => current === segment.key ? null : current)}
                onFocus={() => setActiveRisk(segment.key)} onBlur={() => setActiveRisk((current) => current === segment.key ? null : current)}
                onClick={() => setActiveRisk((current) => current === segment.key ? null : segment.key)} aria-pressed={activeRisk === segment.key}>
                <i style={{ backgroundColor: segment.color }} /><span className="risk-legend-name">{segment.label}</span>
                <strong>{segment.value.toLocaleString()}</strong><small>{segment.percentage.toFixed(1)}%</small>
              </button>
            ))}
            <p className="risk-legend-note">Percentages are calculated from the saved predictions shown above.</p>
          </div>
        </div>
      )}
    </section>
  );
}
