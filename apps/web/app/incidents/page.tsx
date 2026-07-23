import Link from "next/link";

import { apiGet, formatDuration, formatUtc, type Incident, type Service } from "@/lib/api";

type Search = Promise<{ status?: string; severity?: string; service_id?: string }>;

export default async function IncidentsPage({ searchParams }: { searchParams: Search }) {
  const filters = await searchParams;
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.severity) query.set("severity", filters.severity);
  if (filters.service_id) query.set("service_id", filters.service_id);
  const [incidents, services] = await Promise.all([
    apiGet<Incident[]>(`/api/v1/incidents?${query}`, []),
    apiGet<Service[]>("/api/v1/services", []),
  ]);

  return (
    <main>
      <nav aria-label="Primary navigation">
        <Link className="brand" href="/">Causa<span>Ops</span></Link>
        <div className="nav-links"><Link href="/">Overview</Link><Link aria-current="page" href="/incidents">Incidents</Link></div>
        <span className="phase">Phase 4 · Diagnosis</span>
      </nav>
      <header className="page-header">
        <p className="eyebrow">Incident history</p>
        <h1>Incidents</h1>
        <p className="lede">Threshold breaches created from stored telemetry and grouped by service.</p>
      </header>
      <form className="filters" method="get">
        <label>Status<select name="status" defaultValue={filters.status ?? ""}><option value="">All</option><option value="detected">Detected</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></label>
        <label>Severity<select name="severity" defaultValue={filters.severity ?? ""}><option value="">All</option>{["low", "medium", "high", "critical"].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Service<select name="service_id" defaultValue={filters.service_id ?? ""}><option value="">All</option>{services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
        <button type="submit">Apply filters</button>
      </form>
      {incidents.length === 0 ? (
        <div className="empty-state"><h2>No matching incidents</h2><p>Try changing the filters or generate the controlled timeout scenario.</p></div>
      ) : (
        <div className="incident-list incident-table">
          {incidents.map((incident) => (
            <Link className="incident-row" href={`/incidents/${incident.id}`} key={incident.id}>
              <span className={`severity severity-${incident.severity}`}>{incident.severity}</span>
              <span className="incident-main"><strong>{incident.title}</strong><small>{incident.service.name} · {incident.event_count} related events</small></span>
              <span className="incident-meta"><small>Started</small>{formatUtc(incident.started_at)} UTC</span>
              <span className="incident-meta"><small>Duration</small>{formatDuration(incident.started_at, incident.resolved_at)}</span>
              <span className={`incident-status status-${incident.status}`}>{incident.status.replaceAll("_", " ")}</span>
            </Link>
          ))}
        </div>
      )}
      <footer><span>CausaOps</span><span>Facts first. Humans in control.</span></footer>
    </main>
  );
}
