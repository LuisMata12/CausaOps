import asyncio
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator, Literal

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.telemetry import TelemetryClient, new_trace_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()
telemetry = TelemetryClient(settings)
current_mode: Literal["stable", "timeout"] = "stable"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if not app.dependency_overrides:
        await telemetry.ensure_registered()
    yield
    await telemetry.close()


app = FastAPI(title="CausaOps Demo Payments", version="1.0.0", lifespan=lifespan)


class PaymentRequest(BaseModel):
    amount: float = Field(gt=0, le=100_000)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class ModeRequest(BaseModel):
    mode: Literal["stable", "timeout"]


def get_telemetry() -> TelemetryClient:
    return telemetry


def version_for(mode: str) -> str:
    return "1.1.0-timeout" if mode == "timeout" else "1.0.0"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": current_mode, "version": version_for(current_mode)}


@app.post("/admin/mode")
async def set_mode(payload: ModeRequest, client: TelemetryClient = Depends(get_telemetry)) -> dict[str, str]:
    global current_mode
    current_mode = payload.mode
    version = version_for(current_mode)
    await client.record_deployment(current_mode, version)
    return {"mode": current_mode, "version": version}


@app.post("/payments")
async def create_payment(
    payload: PaymentRequest,
    x_request_id: str | None = Header(default=None),
    client: TelemetryClient = Depends(get_telemetry),
) -> JSONResponse:
    trace_id = x_request_id or new_trace_id()
    mode = current_mode
    version = version_for(mode)
    started = perf_counter()
    delay = settings.timeout_delay_seconds if mode == "timeout" else settings.stable_delay_seconds
    await asyncio.sleep(delay)
    status_code = 504 if mode == "timeout" else 201
    duration_ms = round((perf_counter() - started) * 1000)
    await client.record_request(
        trace_id=trace_id,
        version=version,
        duration_ms=duration_ms,
        status_code=status_code,
    )
    body = (
        {"error": "payment_gateway_timeout", "trace_id": trace_id}
        if status_code == 504
        else {
            "id": f"pay_{trace_id[:12]}",
            "status": "approved",
            "amount": payload.amount,
            "currency": payload.currency,
            "trace_id": trace_id,
        }
    )
    return JSONResponse(status_code=status_code, content=body)
