import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import (
    Deployment,
    Incident,
    IncidentEvidence,
    MetricSample,
    Service,
    TelemetryEvent,
)

OPEN_STATUSES = ("detected", "investigating", "awaiting_approval", "mitigating", "monitoring")


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def is_error(event: TelemetryEvent) -> bool:
    status_code = event.attributes.get("status_code")
    return event.level in {"error", "critical"} or (
        isinstance(status_code, int) and status_code >= 500
    )


@dataclass
class DetectionSnapshot:
    service: Service
    window_start: datetime
    window_end: datetime
    request_events: list[TelemetryEvent]
    error_events: list[TelemetryEvent]
    health_events: list[TelemetryEvent]
    health_failures: list[TelemetryEvent]
    durations_ms: list[float]
    p95_latency_ms: float | None
    last_deployment: Deployment | None
    deployment_age_minutes: float | None
    active_rules: list[str]

    @property
    def request_count(self) -> int:
        return len(self.request_events)

    @property
    def error_count(self) -> int:
        return len(self.error_events)

    @property
    def error_rate(self) -> float:
        return self.error_count / self.request_count if self.request_count else 0.0

    def context(self, settings: Settings) -> dict[str, Any]:
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "p95_latency_ms": self.p95_latency_ms,
            "health_check_count": len(self.health_events),
            "health_check_failures": len(self.health_failures),
            "active_rules": self.active_rules,
            "thresholds": {
                "minimum_request_count": settings.minimum_request_count,
                "error_rate": settings.error_rate_threshold,
                "latency_p95_ms": settings.latency_p95_threshold_ms,
                "health_check_failures": settings.health_check_failure_threshold,
            },
            "deployment_age_minutes": self.deployment_age_minutes,
        }


def collect_snapshot(
    db: Session,
    service: Service,
    now: datetime,
    settings: Settings,
) -> DetectionSnapshot:
    window_start = now - timedelta(minutes=settings.detection_window_minutes)
    events = list(
        db.scalars(
            select(TelemetryEvent)
            .where(
                TelemetryEvent.service_id == service.id,
                TelemetryEvent.timestamp >= window_start,
                TelemetryEvent.timestamp <= now,
            )
            .order_by(TelemetryEvent.timestamp)
        )
    )
    request_events = [event for event in events if event.event_type == "request"]
    error_events = [event for event in request_events if is_error(event)]
    health_events = [event for event in events if event.event_type == "health_check"]
    health_failures = [event for event in health_events if is_error(event)]
    durations_ms = list(
        db.scalars(
            select(MetricSample.value).where(
                MetricSample.service_id == service.id,
                MetricSample.metric_name == "http.server.duration",
                MetricSample.timestamp >= window_start,
                MetricSample.timestamp <= now,
            )
        )
    )
    p95_latency_ms = percentile(durations_ms, 0.95)
    last_deployment = db.scalar(
        select(Deployment)
        .where(Deployment.service_id == service.id, Deployment.timestamp <= now)
        .order_by(Deployment.timestamp.desc())
        .limit(1)
    )
    deployment_age_minutes = None
    if last_deployment is not None:
        deployment_age_minutes = (now - as_utc(last_deployment.timestamp)).total_seconds() / 60

    request_volume_ready = len(request_events) >= settings.minimum_request_count
    error_rate = len(error_events) / len(request_events) if request_events else 0.0
    active_rules: list[str] = []
    if request_volume_ready and error_rate > settings.error_rate_threshold:
        active_rules.append("high_error_rate")
    if (
        request_volume_ready
        and p95_latency_ms is not None
        and p95_latency_ms > settings.latency_p95_threshold_ms
    ):
        active_rules.append("high_p95_latency")
    if len(health_failures) >= settings.health_check_failure_threshold:
        active_rules.append("repeated_health_check_failures")

    return DetectionSnapshot(
        service=service,
        window_start=window_start,
        window_end=now,
        request_events=request_events,
        error_events=error_events,
        health_events=health_events,
        health_failures=health_failures,
        durations_ms=durations_ms,
        p95_latency_ms=p95_latency_ms,
        last_deployment=last_deployment,
        deployment_age_minutes=deployment_age_minutes,
        active_rules=active_rules,
    )


def severity_for(snapshot: DetectionSnapshot, settings: Settings) -> str:
    if snapshot.error_rate >= 0.5 or (snapshot.p95_latency_ms or 0) >= 5000:
        return "critical"
    deployment_is_recent = (
        snapshot.deployment_age_minutes is not None
        and 0 <= snapshot.deployment_age_minutes <= settings.deployment_correlation_minutes
    )
    return "high" if deployment_is_recent or len(snapshot.active_rules) > 1 else "medium"


def highest_severity(current: str, candidate: str) -> str:
    severity_order = {"medium": 0, "high": 1, "critical": 2}
    return max((current, candidate), key=lambda severity: severity_order[severity])


def summary_for(snapshot: DetectionSnapshot) -> str:
    signals: list[str] = []
    if "high_error_rate" in snapshot.active_rules:
        signals.append(f"{snapshot.error_rate:.1%} error rate")
    if "high_p95_latency" in snapshot.active_rules:
        signals.append(f"{snapshot.p95_latency_ms:.0f} ms p95 latency")
    if "repeated_health_check_failures" in snapshot.active_rules:
        signals.append(f"{len(snapshot.health_failures)} failed health checks")
    return f"Deterministic rules detected {' and '.join(signals)} in the current window."


def upsert_evidence(
    db: Session,
    incident: Incident,
    evidence_type: str,
    reference_id: str,
    description: str,
    timestamp: datetime,
    payload: dict[str, Any],
) -> None:
    evidence = db.scalar(
        select(IncidentEvidence).where(
            IncidentEvidence.incident_id == incident.id,
            IncidentEvidence.evidence_type == evidence_type,
            IncidentEvidence.reference_id == reference_id,
        )
    )
    if evidence is None:
        db.add(
            IncidentEvidence(
                incident_id=incident.id,
                evidence_type=evidence_type,
                reference_id=reference_id,
                description=description,
                timestamp=timestamp,
                payload=payload,
            )
        )
    else:
        evidence.description = description
        evidence.timestamp = timestamp
        evidence.payload = payload


def attach_evidence(
    db: Session,
    incident: Incident,
    snapshot: DetectionSnapshot,
    settings: Settings,
) -> None:
    for event in [*snapshot.error_events, *snapshot.health_failures]:
        upsert_evidence(
            db,
            incident,
            "telemetry_event",
            str(event.id),
            event.message,
            event.timestamp,
            {
                "trace_id": event.trace_id,
                "level": event.level,
                "version": event.version,
                "duration_ms": event.duration_ms,
                "metadata": event.attributes,
            },
        )
    if (
        incident.deployment_id is not None
        and snapshot.last_deployment is not None
        and snapshot.last_deployment.id == incident.deployment_id
    ):
        deployment = snapshot.last_deployment
        upsert_evidence(
            db,
            incident,
            "deployment",
            str(deployment.id),
            f"Deployment {deployment.version} occurred before the detected degradation.",
            deployment.timestamp,
            {
                "version": deployment.version,
                "commit_sha": deployment.commit_sha,
                "changed_files": deployment.changed_files,
                "age_minutes": snapshot.deployment_age_minutes,
            },
        )
    upsert_evidence(
        db,
        incident,
        "deterministic_analysis",
        "latest-window",
        "Backend-calculated metrics used by the detection rules.",
        snapshot.window_end,
        snapshot.context(settings),
    )


@dataclass
class DetectionRunResult:
    services_checked: int = 0
    incidents_created: int = 0
    incidents_updated: int = 0
    incidents_resolved: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "services_checked": self.services_checked,
            "incidents_created": self.incidents_created,
            "incidents_updated": self.incidents_updated,
            "incidents_resolved": self.incidents_resolved,
        }


def run_detection(
    db: Session,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> DetectionRunResult:
    settings = settings or get_settings()
    now = as_utc(now or datetime.now(UTC))
    services = list(db.scalars(select(Service).order_by(Service.name)))
    result = DetectionRunResult(services_checked=len(services))

    for service in services:
        snapshot = collect_snapshot(db, service, now, settings)
        incident = db.scalar(
            select(Incident)
            .where(Incident.service_id == service.id, Incident.status.in_(OPEN_STATUSES))
            .order_by(Incident.detected_at.desc())
            .limit(1)
        )
        if snapshot.active_rules:
            recent_deployment = (
                snapshot.last_deployment
                if snapshot.deployment_age_minutes is not None
                and 0 <= snapshot.deployment_age_minutes <= settings.deployment_correlation_minutes
                else None
            )
            bad_events = [*snapshot.error_events, *snapshot.health_failures]
            started_at = min(
                (as_utc(event.timestamp) for event in bad_events),
                default=snapshot.window_start,
            )
            if incident is None:
                incident = Incident(
                    service_id=service.id,
                    deployment_id=recent_deployment.id if recent_deployment else None,
                    fingerprint=f"{service.id}:service-degradation",
                    title=f"Degradation detected in {service.name}",
                    severity=severity_for(snapshot, settings),
                    status="detected",
                    started_at=started_at,
                    detected_at=now,
                    event_count=len(bad_events),
                    summary=summary_for(snapshot),
                    detection_context=snapshot.context(settings),
                )
                db.add(incident)
                db.flush()
                result.incidents_created += 1
            else:
                incident.deployment_id = incident.deployment_id or (
                    recent_deployment.id if recent_deployment else None
                )
                incident.severity = highest_severity(
                    incident.severity,
                    severity_for(snapshot, settings),
                )
                incident.event_count = len(bad_events)
                incident.summary = summary_for(snapshot)
                incident.detection_context = snapshot.context(settings)
                result.incidents_updated += 1
            attach_evidence(db, incident, snapshot, settings)
        elif incident is not None:
            recovery_observed = (
                snapshot.request_count >= settings.minimum_request_count
                or len(snapshot.health_events) >= settings.health_check_failure_threshold
            )
            if recovery_observed:
                incident.status = "resolved"
                incident.resolved_at = now
                incident.summary = "Recovery verified by deterministic telemetry in the latest window."
                incident.detection_context = snapshot.context(settings)
                result.incidents_resolved += 1

    db.commit()
    return result
