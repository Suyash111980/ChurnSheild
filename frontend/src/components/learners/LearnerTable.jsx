import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

const columns = [
  ["id_student", "Learner"],
  ["code_module", "Module"],
  ["code_presentation", "Presentation"],
  ["highest_education", "Education"],
  ["region", "Region"],
];

function displayName(learner) {
  const name = typeof learner.student_name === "string" ? learner.student_name.trim() : "";
  if (name) return name;
  return learner.id_student != null ? `Learner ${learner.id_student}` : `Learner ${learner.id}`;
}

function valueOrDash(value) {
  return value == null || value === "" ? "—" : String(value);
}

export default function LearnerTable({ learners, sort, direction, onSort }) {
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
          {learners.map((learner) => (
            <tr key={learner.id}>
              <td>
                <div className="learner-cell">
                  <span className="learner-avatar">{String(learner.id_student ?? "L").slice(0, 2)}</span>
                  <span><strong>{displayName(learner)}</strong><small>ID {valueOrDash(learner.id_student)}</small></span>
                </div>
              </td>
              <td>{valueOrDash(learner.code_module)}</td>
              <td>{valueOrDash(learner.code_presentation)}</td>
              <td>{valueOrDash(learner.highest_education)}</td>
              <td>{valueOrDash(learner.region)}</td>
              <td><Link className="record-link profile-link" to={`/learners/${encodeURIComponent(learner.id)}`}>View profile <ExternalLink size={13} /></Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
