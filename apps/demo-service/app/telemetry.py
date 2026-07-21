import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class TelemetryClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(base_url=settings.causaops_api_url, timeout=3)
        self.service_id: str | None = None

    async def close(self) -> None:
        await self.client.aclose()

    async def ensure_registered(self) -> str | None:
        if self.service_id is not None:
            return self.service_id
        try:
            response = await self.client.post(
                "/api/v1/services",
                json={"name": self.settings.service_name, "environment": self.settings.environment},
            )
            response.raise_for_status()
            self.service_id = response.json()["id"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("telemetry_registration_failed error=%s", type(exc).__name__)
        return self.service_id

    async def send(self, path: str, payload: dict[str, Any]) -> None:
        service_id = await self.ensure_registered()
        if service_id is None:
            return
        try:
            response = await self.client.post(path, json={"service_id": service_id, **payload})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("telemetry_delivery_failed path=%s error=%s", path, type(exc).__name__)

    async def record_request(
        self,
        *,
        trace_id: str,
        version: str,
        duration_ms: int,
        status_code: int,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        level = "error" if status_code >= 500 else "info"
        await self.send(
            "/api/v1/telemetry/events",
            {
                "event_type": "request",
                "level": level,
                "message": "Payment request timed out" if status_code == 504 else "Payment processed",
                "timestamp": now,
                "trace_id": trace_id,
                "version": version,
                "duration_ms": duration_ms,
                "metadata": {"route": "/payments", "status_code": status_code},
            },
        )
        await self.send(
            "/api/v1/telemetry/metrics",
            {
                "metric_name": "http.server.duration",
                "value": duration_ms,
                "timestamp": now,
                "labels": {"route": "/payments", "status": str(status_code), "version": version},
            },
        )

    async def record_deployment(self, mode: str, version: str) -> None:
        await self.send(
            "/api/v1/deployments",
            {
                "version": version,
                "commit_sha": "badcafe1234" if mode == "timeout" else "57ab1e00000",
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "succeeded" if mode == "timeout" else "rolled_back",
                "changed_files": ["app/payment_gateway.py", "config/timeouts.py"],
                "metadata": {"mode": mode, "controlled_demo": True},
            },
        )


def new_trace_id() -> str:
    return uuid.uuid4().hex

