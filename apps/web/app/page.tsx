type Health = {
  live: boolean;
  ready: boolean;
  demo: boolean;
  checkedAt: string;
};

async function getHealth(): Promise<Health> {
  const baseUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const checkedAt = new Date().toISOString();
  const demoUrl = process.env.DEMO_INTERNAL_URL ?? "http://localhost:8100";
  const isHealthy = async (url: string) => {
    try {
      return (await fetch(url, { cache: "no-store" })).ok;
    } catch {
      return false;
    }
  };
  const [live, ready, demo] = await Promise.all([
    isHealthy(`${baseUrl}/health/live`),
    isHealthy(`${baseUrl}/health/ready`),
    isHealthy(`${demoUrl}/health`),
  ]);
  return { live, ready, demo, checkedAt };
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
  const allOperational = health.live && health.ready && health.demo;

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
          <StatusCard label="Demo Service" healthy={health.demo} detail="Controlled payments simulation" />
        </div>
        <p className="timestamp">Last checked {new Date(health.checkedAt).toLocaleString("en", { timeZone: "UTC" })} UTC</p>
      </section>

      <footer><span>CausaOps</span><span>Facts first. Humans in control.</span></footer>
    </main>
  );
}
