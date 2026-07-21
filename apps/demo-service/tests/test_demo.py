import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app, get_telemetry
from app.telemetry import TelemetryClient


class FakeTelemetry:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.deployments: list[tuple[str, str]] = []

    async def record_request(self, **payload: object) -> None:
        self.requests.append(payload)

    async def record_deployment(self, mode: str, version: str) -> None:
        self.deployments.append((mode, version))


def test_controlled_timeout_and_recovery() -> None:
    fake = FakeTelemetry()
    app.dependency_overrides[get_telemetry] = lambda: fake
    settings = get_settings()
    original_stable = settings.stable_delay_seconds
    original_timeout = settings.timeout_delay_seconds
    settings.stable_delay_seconds = 0
    settings.timeout_delay_seconds = 0
    try:
        with TestClient(app) as client:
            assert client.post("/admin/mode", json={"mode": "timeout"}).status_code == 200
            failed = client.post("/payments", json={"amount": 25, "currency": "USD"})
            assert failed.status_code == 504
            assert fake.requests[-1]["version"] == "1.1.0-timeout"

            assert client.post("/admin/mode", json={"mode": "stable"}).status_code == 200
            recovered = client.post("/payments", json={"amount": 25, "currency": "USD"})
            assert recovered.status_code == 201
            assert fake.deployments == [("timeout", "1.1.0-timeout"), ("stable", "1.0.0")]
    finally:
        settings.stable_delay_seconds = original_stable
        settings.timeout_delay_seconds = original_timeout
        app.dependency_overrides.clear()


def test_telemetry_client_registers_and_emits_request_facts() -> None:
    received: list[tuple[str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        received.append((request.url.path, payload))
        if request.url.path == "/api/v1/services":
            return httpx.Response(200, json={"id": "service-123"})
        return httpx.Response(201, json={"id": "fact-123"})

    async def scenario() -> None:
        http = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://causaops.test",
        )
        client = TelemetryClient(Settings(), client=http)
        await client.record_request(
            trace_id="trace-123",
            version="1.1.0-timeout",
            duration_ms=2500,
            status_code=504,
        )
        await client.close()

    asyncio.run(scenario())
    assert [path for path, _ in received] == [
        "/api/v1/services",
        "/api/v1/telemetry/events",
        "/api/v1/telemetry/metrics",
    ]
    assert received[1][1]["trace_id"] == "trace-123"
    assert received[2][1]["value"] == 2500
