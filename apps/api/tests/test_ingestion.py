from datetime import UTC, datetime

from fastapi.testclient import TestClient


def register(client: TestClient) -> str:
    response = client.post(
        "/api/v1/services",
        json={"name": "demo-service", "environment": "development"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_service_registration_is_idempotent(client: TestClient) -> None:
    first_id = register(client)
    second_id = register(client)
    assert first_id == second_id
    assert len(client.get("/api/v1/services").json()) == 1


def test_ingests_and_lists_demo_facts(client: TestClient) -> None:
    service_id = register(client)
    timestamp = datetime.now(UTC).isoformat()

    event = client.post(
        "/api/v1/telemetry/events",
        json={
            "service_id": service_id,
            "event_type": "request",
            "level": "error",
            "message": "Payment request timed out",
            "timestamp": timestamp,
            "trace_id": "trace-test",
            "version": "1.1.0-timeout",
            "duration_ms": 2500,
            "metadata": {"route": "/payments", "status_code": 504},
        },
    )
    metric = client.post(
        "/api/v1/telemetry/metrics",
        json={
            "service_id": service_id,
            "metric_name": "http.server.duration",
            "value": 2500,
            "timestamp": timestamp,
            "labels": {"route": "/payments", "status": "504"},
        },
    )
    deployment = client.post(
        "/api/v1/deployments",
        json={
            "service_id": service_id,
            "version": "1.1.0-timeout",
            "commit_sha": "badcafe1234",
            "timestamp": timestamp,
            "status": "succeeded",
            "changed_files": ["app/payment.py"],
            "metadata": {"mode": "timeout"},
        },
    )

    assert event.status_code == 201
    assert event.json()["metadata"]["status_code"] == 504
    assert metric.status_code == 201
    assert deployment.status_code == 201
    assert len(client.get(f"/api/v1/telemetry/events?service_id={service_id}").json()) == 1
    assert len(client.get(f"/api/v1/telemetry/metrics?service_id={service_id}").json()) == 1
    assert len(client.get(f"/api/v1/deployments?service_id={service_id}").json()) == 1


def test_rejects_unknown_service(client: TestClient) -> None:
    response = client.post(
        "/api/v1/telemetry/events",
        json={
            "service_id": "3dca1c75-6635-45ac-8e13-c46720b29a51",
            "event_type": "log",
            "level": "info",
            "message": "Not persisted",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 404
