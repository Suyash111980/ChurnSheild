import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";

export default function OuladOverview() {
  usePageTransitionReady(true);
  return <>
    <PageHeader
      eyebrow="PLATFORM DATA"
      title="OULAD workspace"
      subtitle="Prepared OULAD data can only be imported into an explicitly owned Admin workspace."
    />
    <section className="panel" aria-labelledby="oulad-import-unavailable">
      <h2 id="oulad-import-unavailable">Import is unavailable for Master Admin</h2>
      <p role="status">
        Master Admin accounts do not own a customer workspace. ChurnShield cannot
        assign this dataset to an Admin workspace until an authorized ownership
        workflow is defined. No data was uploaded.
      </p>
      <Link className="text-button" to="/master-admin">Return to Platform Overview</Link>
    </section>
  </>;
}
