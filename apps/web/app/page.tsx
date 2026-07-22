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
  const [health, incidents] = await Promise.all([
    getHealth(),
    apiGet<Incident[]>("/api/v1/incidents?limit=5", []),
  ]);
  const allOperational = health.live && health.ready && health.demo;
  const activeIncidents = incidents.filter((incident) => incident.status !== "resolved");

  return (
    <main>
      <nav aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="CausaOps home">Causa<span>Ops</span></a>
        <div className="nav-links"><Link href="/">Overview</Link><Link href="/incidents">Incidents</Link></div>
        <span className="phase">Phase 3 · Detection</span>
      </nav>

      <section className="hero" id="top">
        <p className="eyebrow">Incident intelligence, grounded in evidence</p>
        <h1>Find the cause.<br /><span>Verify the fix.</span></h1>
        <p className="lede">
          CausaOps connects telemetry, deployments, and human-approved actions into one auditable incident workflow.
        </p>
      </section>

      <section aria-labelledby="incident-overview" className="status-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Deterministic detection</p>
            <h2 id="incident-overview">Incident overview</h2>
          </div>
          <Link className="text-link" href="/incidents">View all incidents →</Link>
        </div>
        <div className="metric-grid">
          <article className="metric-card"><span>Active incidents</span><strong>{activeIncidents.length}</strong></article>
          <article className="metric-card"><span>Total detected</span><strong>{incidents.length}</strong></article>
          <article className="metric-card"><span>Detection method</span><strong className="metric-label">Rules</strong></article>
        </div>
        {incidents.length === 0 ? (
          <div className="empty-state"><h3>No incidents detected</h3><p>The detector has not found a threshold breach in the current telemetry window.</p></div>
        ) : (
          <div className="incident-list">
            {incidents.map((incident) => (
              <Link className="incident-row" href={`/incidents/${incident.id}`} key={incident.id}>
                <span className={`severity severity-${incident.severity}`}>{incident.severity}</span>
                <span className="incident-main"><strong>{incident.title}</strong><small>{incident.service.name} · {formatUtc(incident.detected_at)} UTC</small></span>
                <span className={`incident-status status-${incident.status}`}>{incident.status.replaceAll("_", " ")}</span>
              </Link>
            ))}
          </div>
        )}
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
import Link from "next/link";

import { apiGet, formatUtc, type Incident } from "@/lib/api";
