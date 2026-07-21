from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Deployment, MetricSample, Service, TelemetryEvent


def seed() -> None:
    with SessionLocal() as db:
        service = db.scalar(
            select(Service).where(
                Service.name == "seeded-demo-payments",
                Service.environment == "development",
            )
        )
        if service is not None:
            print("Seed data already exists; no changes made.")
            return

        service = Service(
            name="seeded-demo-payments",
            environment="development",
            status="degraded",
        )
        db.add(service)
        db.flush()
        deployed_at = datetime.now(UTC) - timedelta(minutes=8)
        db.add(
            Deployment(
                service_id=service.id,
                version="1.1.0-timeout",
                commit_sha="badcafe1234",
                timestamp=deployed_at,
                status="succeeded",
                changed_files=["app/payment_gateway.py", "config/timeouts.py"],
                attributes={"mode": "timeout", "seeded": True},
            )
        )
        for index in range(5):
            timestamp = deployed_at + timedelta(minutes=index + 1)
            is_error = index >= 2
            status_code = 504 if is_error else 201
            duration_ms = 2500 if is_error else 80
            db.add_all(
                [
                    TelemetryEvent(
                        service_id=service.id,
                        event_type="request",
                        level="error" if is_error else "info",
                        message="Payment request timed out" if is_error else "Payment processed",
                        timestamp=timestamp,
                        trace_id=f"seed-trace-{index}",
                        version="1.1.0-timeout",
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
        db.commit()
        print("Seeded one service, one deployment, five events, and five metrics.")


if __name__ == "__main__":
    seed()
