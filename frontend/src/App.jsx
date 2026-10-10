export default function App() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
  return (
    <main className="shell">
      <div className="brand-mark" aria-hidden="true">C</div>
      <p className="eyebrow">Learner retention intelligence</p>
      <h1>ChurnShield</h1>
      <p className="intro">The project foundation is ready. Dashboard workflows will connect to the ChurnShield API as the team builds each milestone.</p>
      <a href={`${apiBase}/health`}>Check API health</a>
    </main>
  );
}
