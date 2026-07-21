type Health = {
  live: boolean;
  ready: boolean;
  checkedAt: string;
};

async function getHealth(): Promise<Health> {
  const baseUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const checkedAt = new Date().toISOString();

  try {
    const [live, ready] = await Promise.all([
      fetch(`${baseUrl}/health/live`, { cache: "no-store" }),
      fetch(`${baseUrl}/health/ready`, { cache: "no-store" }),
    ]);
    return { live: live.ok, ready: ready.ok, checkedAt };
  } catch {
    return { live: false, ready: false, checkedAt };
  }
}

function StatusCard({ label, healthy, detail }: { label: string; healthy: boolean; detail: string }) {
  return (
    <article className="card">
      <div className="card-heading">
        <span className={`indicator ${healthy ? "healthy" : "unavailable"}`} aria-hidden="true" />
        <h2>{label}</h2>
      </div>
      <p className={healthy ? "status-healthy" : "status-unavailable"}>
        {healthy ? "Operational" : "Unavailable"}
      </p>
      <p className="detail">{detail}</p>
    </article>
  );
}

export default async function Home() {
  const health = await getHealth();
  const allOperational = health.live && health.ready;

  return (
    <main>
      <nav aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="CausaOps home">Causa<span>Ops</span></a>
        <span className="phase">Phase 1 · Foundation</span>
      </nav>

      <section className="hero" id="top">
        <p className="eyebrow">Incident intelligence, grounded in evidence</p>
        <h1>Find the cause.<br /><span>Verify the fix.</span></h1>
        <p className="lede">
          CausaOps connects telemetry, deployments, and human-approved actions into one auditable incident workflow.
        </p>
      </section>

      <section aria-labelledby="system-status" className="status-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Local environment</p>
            <h2 id="system-status">System status</h2>
          </div>
          <div className={`summary ${allOperational ? "healthy" : "unavailable"}`}>
            {allOperational ? "All systems operational" : "Setup needs attention"}
          </div>
        </div>
        <div className="grid">
          <StatusCard label="CausaOps API" healthy={health.live} detail="FastAPI process liveness" />
          <StatusCard label="PostgreSQL" healthy={health.ready} detail="Verified through an API database query" />
          <article className="card pending">
            <div className="card-heading"><span className="indicator planned" aria-hidden="true" /><h2>Demo Service</h2></div>
            <p className="status-planned">Planned</p>
            <p className="detail">Introduced in Phase 2</p>
          </article>
        </div>
        <p className="timestamp">Last checked {new Date(health.checkedAt).toLocaleString("en", { timeZone: "UTC" })} UTC</p>
      </section>

      <footer><span>CausaOps</span><span>Facts first. Humans in control.</span></footer>
    </main>
  );
}

