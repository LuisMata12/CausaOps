import Link from "next/link";
import { notFound } from "next/navigation";

import { apiGet, formatDuration, formatUtc, type Incident } from "@/lib/api";

export default async function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const incident = await apiGet<Incident | null>(`/api/v1/incidents/${id}`, null);
  if (!incident) notFound();
  const context = incident.detection_context;

  return (
    <main>
      <nav aria-label="Primary navigation">
        <Link className="brand" href="/">Causa<span>Ops</span></Link>
        <div className="nav-links"><Link href="/">Overview</Link><Link href="/incidents">Incidents</Link></div>
        <span className="phase">Phase 3 · Detection</span>
      </nav>
      <div className="breadcrumb"><Link href="/incidents">Incidents</Link><span>/</span><span>{incident.id.slice(0, 8)}</span></div>
      <header className="incident-header">
        <div><span className={`severity severity-${incident.severity}`}>{incident.severity}</span><h1>{incident.title}</h1><p>{incident.summary}</p></div>
        <span className={`incident-status status-${incident.status}`}>{incident.status.replaceAll("_", " ")}</span>
      </header>
      <section className="fact-panel" aria-labelledby="facts-heading">
        <div className="section-heading"><div><p className="eyebrow">Backend calculations</p><h2 id="facts-heading">Verified facts</h2></div><span className="fact-label">Deterministic</span></div>
        <div className="metric-grid four">
          <article className="metric-card"><span>Error rate</span><strong>{((context.error_rate ?? 0) * 100).toFixed(1)}%</strong><small>{context.error_count ?? 0} / {context.request_count ?? 0} requests</small></article>
          <article className="metric-card"><span>Latency p95</span><strong>{context.p95_latency_ms == null ? "—" : `${Math.round(context.p95_latency_ms)} ms`}</strong></article>
          <article className="metric-card"><span>Related events</span><strong>{incident.event_count}</strong></article>
          <article className="metric-card"><span>Duration</span><strong>{formatDuration(incident.started_at, incident.resolved_at)}</strong></article>
        </div>
        <div className="rule-list">{(context.active_rules ?? []).map((rule) => <span key={rule}>{rule.replaceAll("_", " ")}</span>)}</div>
      </section>
      <div className="detail-grid">
        <section className="detail-section"><h2>Timeline & evidence</h2><div className="timeline">{incident.evidence?.map((item) => <article className="timeline-item" key={item.id}><span className="timeline-dot" /><div><small>{formatUtc(item.timestamp)} UTC · {item.evidence_type.replaceAll("_", " ")}</small><h3>{item.description}</h3><code>{item.reference_id}</code></div></article>)}</div></section>
        <aside className="detail-aside"><h2>Correlation</h2><dl><dt>Service</dt><dd>{incident.service.name}</dd><dt>Environment</dt><dd>{incident.service.environment}</dd><dt>Detected</dt><dd>{formatUtc(incident.detected_at)} UTC</dd><dt>Deployment</dt><dd>{incident.deployment?.version ?? "No recent deployment"}</dd>{incident.deployment && <><dt>Commit</dt><dd><code>{incident.deployment.commit_sha}</code></dd><dt>Changed files</dt><dd>{incident.deployment.changed_files.join(", ")}</dd></>}</dl><p className="aside-note">No AI inference has been generated. All information on this page comes from stored telemetry and deterministic calculations.</p></aside>
      </div>
      <footer><span>CausaOps</span><span>Facts first. Humans in control.</span></footer>
    </main>
  );
}
