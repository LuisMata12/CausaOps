from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.detection import highest_severity, percentile, run_detection
from app.models import Deployment, Incident, IncidentEvidence, MetricSample, Service, TelemetryEvent


def add_request(
    db: Session,
    service: Service,
    timestamp: datetime,
    *,
    status_code: int,
    duration_ms: int,
    trace_id: str,
) -> None:
    db.add_all(
        [
            TelemetryEvent(
                service_id=service.id,
                event_type="request",
                level="error" if status_code >= 500 else "info",
                message="Payment request timed out" if status_code >= 500 else "Payment processed",
                timestamp=timestamp,
                trace_id=trace_id,
                version="1.1.0-timeout" if status_code >= 500 else "1.0.0",
                duration_ms=duration_ms,
                attributes={"route": "/payments", "status_code": status_code},
            ),
            MetricSample(
                service_id=service.id,
                metric_name="http.server.duration",
                value=duration_ms,
                timestamp=timestamp,
                labels={"route": "/payments", "status": str(status_code)},
            ),
        ]
    )


def test_nearest_rank_percentile() -> None:
    assert percentile([], 0.95) is None
    assert percentile([10, 20, 30, 40, 50], 0.95) == 50


def test_incident_severity_never_downgrades() -> None:
    assert highest_severity("critical", "high") == "critical"
    assert highest_severity("high", "medium") == "high"
    assert highest_severity("medium", "critical") == "critical"


def test_detector_groups_evidence_and_resolves_after_recovery(db_session: Session) -> None:
    now = datetime(2026, 7, 21, 18, 0, tzinfo=UTC)
    service = Service(name="demo-payments", environment="test", status="operational")
    db_session.add(service)
    db_session.flush()
    deployment = Deployment(
        service_id=service.id,
        version="1.1.0-timeout",
        commit_sha="badcafe1234",
        timestamp=now - timedelta(minutes=1),
        status="succeeded",
        changed_files=["config/timeouts.py"],
        attributes={"mode": "timeout"},
    )
    db_session.add(deployment)
    for index, status_code in enumerate([201, 201, 201, 504, 504]):
        add_request(
            db_session,
            service,
            now - timedelta(seconds=30 - index),
            status_code=status_code,
            duration_ms=2500 if status_code == 504 else 50,
            trace_id=f"initial-{index}",
        )
    db_session.commit()
    settings = Settings(
        DETECTION_WINDOW_MINUTES=5,
        MINIMUM_REQUEST_COUNT=5,
        ERROR_RATE_THRESHOLD=0.10,
        LATENCY_P95_THRESHOLD_MS=2000,
    )

    first = run_detection(db_session, now=now, settings=settings)
    second = run_detection(db_session, now=now + timedelta(seconds=1), settings=settings)

    assert first.incidents_created == 1
    assert second.incidents_created == 0
    assert second.incidents_updated == 1
    assert db_session.scalar(select(func.count()).select_from(Incident)) == 1
    incident = db_session.scalar(select(Incident))
    assert incident is not None
    assert incident.severity == "high"
    assert incident.event_count == 2
    assert incident.detection_context["active_rules"] == [
        "high_error_rate",
        "high_p95_latency",
    ]
    assert db_session.scalar(select(func.count()).select_from(IncidentEvidence)) == 4

    recovery_time = now + timedelta(minutes=6)
    for index in range(5):
        add_request(
            db_session,
            service,
            recovery_time - timedelta(seconds=10 - index),
            status_code=201,
            duration_ms=45,
            trace_id=f"recovery-{index}",
        )
    db_session.commit()

    recovered = run_detection(db_session, now=recovery_time, settings=settings)
    db_session.refresh(incident)
    assert recovered.incidents_resolved == 1
    assert incident.status == "resolved"
    assert incident.resolved_at is not None


def test_detection_api_returns_created_incident(client: TestClient) -> None:
    service = client.post(
        "/api/v1/services",
        json={"name": "api-demo", "environment": "test"},
    ).json()
    timestamp = datetime.now(UTC).isoformat()
    for index in range(5):
        response = client.post(
            "/api/v1/telemetry/events",
            json={
                "service_id": service["id"],
                "event_type": "request",
                "level": "error",
                "message": "Request failed",
                "timestamp": timestamp,
                "trace_id": f"api-{index}",
                "duration_ms": 2500,
                "metadata": {"status_code": 504},
            },
        )
        assert response.status_code == 201

    run = client.post("/api/v1/detection/run")
    incidents = client.get("/api/v1/incidents").json()
    detail = client.get(f"/api/v1/incidents/{incidents[0]['id']}")

    assert run.status_code == 200
    assert run.json()["incidents_created"] == 1
    assert len(incidents) == 1
    assert incidents[0]["status"] == "detected"
    assert detail.status_code == 200
    assert len(detail.json()["evidence"]) == 6
