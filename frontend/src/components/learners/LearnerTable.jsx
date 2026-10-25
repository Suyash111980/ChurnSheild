import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

const columns = [
  ["id_student", "Learner"],
  ["highest_education", "Education"],
  ["region", "Region"],
  ["latest_risk_category", "Saved risk"],
  ["latest_risk_probability", "Probability"],
];

function displayName(learner) {
  const name = typeof learner.student_name === "string" ? learner.student_name.trim() : "";
  if (name) return name;
  return learner.id_student != null ? `Learner ${learner.id_student}` : `Learner ${learner.id}`;
}

function valueOrDash(value) {
  return value == null || value === "" ? "—" : String(value);
}

export default function LearnerTable({ learners, sort, direction, onSort, backTo = "/learners", serialOffset = 0 }) {
  return (
    <div className="table-scroll">
      <table className="learner-table api-learner-table">
        <thead><tr>
          {columns.map(([key, label]) => (
            <th key={key} aria-sort={sort === key ? (direction === "asc" ? "ascending" : "descending") : "none"}>
              <button className="sort-button" type="button" onClick={() => onSort(key)}>
                {label}
                {sort === key ? (direction === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} />}
              </button>
            </th>
          ))}
          <th><span className="sr-only">Profile</span></th>
        </tr></thead>
        <tbody>
          {learners.map((learner, index) => (
            <tr key={learner.id}>
              <td>
                <div className="learner-cell">
                  <span className="learner-avatar" aria-label={`Serial number ${serialOffset + index + 1}`}>{serialOffset + index + 1}</span>
                  <span><strong>{displayName(learner)}</strong><small>ID {valueOrDash(learner.id_student)}</small></span>
                </div>
              </td>
              <td>{valueOrDash(learner.highest_education)}</td>
              <td>{valueOrDash(learner.region)}</td>
              <td>{learner.latest_risk_category ? <span className={`risk-badge risk-${learner.latest_risk_category}`} title={`Model ${valueOrDash(learner.latest_model_version)}`}>{learner.latest_risk_category}</span> : <span className="prediction-unavailable">No prediction</span>}</td>
              <td>{learner.latest_risk_probability == null ? "—" : `${(Number(learner.latest_risk_probability) * 100).toFixed(1)}%`}</td>
              <td><Link className="record-link profile-link" to={`/learners/${encodeURIComponent(learner.id)}?dataset_id=${encodeURIComponent(learner.dataset_id)}`} state={{ from: backTo }}>View profile <ExternalLink size={13} /></Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


