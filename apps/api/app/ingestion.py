import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deployment, MetricSample, Service, TelemetryEvent
from app.schemas import (
    DeploymentCreate,
    DeploymentRead,
    MetricSampleCreate,
    MetricSampleRead,
    ServiceCreate,
    ServiceRead,
    TelemetryEventCreate,
    TelemetryEventRead,
)

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


def require_service(db: Session, service_id: uuid.UUID) -> None:
    if db.get(Service, service_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")


@router.post("/services", response_model=ServiceRead)
def register_service(payload: ServiceCreate, db: Session = Depends(get_db)) -> Service:
    existing = db.scalar(
        select(Service).where(
            Service.name == payload.name,
            Service.environment == payload.environment,
        )
    )
    if existing is not None:
        return existing
    service = Service(name=payload.name, environment=payload.environment, status="operational")
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services", response_model=list[ServiceRead])
def list_services(db: Session = Depends(get_db)) -> list[Service]:
    return list(db.scalars(select(Service).order_by(Service.name)))


@router.post("/telemetry/events", response_model=TelemetryEventRead, status_code=201)
def ingest_event(payload: TelemetryEventCreate, db: Session = Depends(get_db)) -> TelemetryEvent:
    require_service(db, payload.service_id)
    event = TelemetryEvent(
        **payload.model_dump(exclude={"metadata"}),
        attributes=payload.metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/telemetry/events", response_model=list[TelemetryEventRead])
def list_events(
    service_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TelemetryEvent]:
    query = select(TelemetryEvent).order_by(TelemetryEvent.timestamp.desc()).limit(limit)
    if service_id is not None:
        query = query.where(TelemetryEvent.service_id == service_id)
    return list(db.scalars(query))


@router.post("/telemetry/metrics", response_model=MetricSampleRead, status_code=201)
def ingest_metric(payload: MetricSampleCreate, db: Session = Depends(get_db)) -> MetricSample:
    require_service(db, payload.service_id)
    sample = MetricSample(**payload.model_dump())
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/telemetry/metrics", response_model=list[MetricSampleRead])
def list_metrics(
    service_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MetricSample]:
    query = select(MetricSample).order_by(MetricSample.timestamp.desc()).limit(limit)
    if service_id is not None:
        query = query.where(MetricSample.service_id == service_id)
    return list(db.scalars(query))


@router.post("/deployments", response_model=DeploymentRead, status_code=201)
def ingest_deployment(payload: DeploymentCreate, db: Session = Depends(get_db)) -> Deployment:
    require_service(db, payload.service_id)
    deployment = Deployment(
        **payload.model_dump(exclude={"metadata"}),
        attributes=payload.metadata,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


@router.get("/deployments", response_model=list[DeploymentRead])
def list_deployments(
    service_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Deployment]:
    query = select(Deployment).order_by(Deployment.timestamp.desc()).limit(limit)
    if service_id is not None:
        query = query.where(Deployment.service_id == service_id)
    return list(db.scalars(query))
