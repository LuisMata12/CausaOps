import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.detection import run_detection
from app.models import Incident
from app.schemas import DetectionRunResponse, IncidentDetail, IncidentRead

router = APIRouter(prefix="/api/v1", tags=["incidents"])


def incident_options():
    return (
        selectinload(Incident.service),
        selectinload(Incident.deployment),
        selectinload(Incident.evidence),
    )


@router.post("/detection/run", response_model=DetectionRunResponse)
def detect(db: Session = Depends(get_db)) -> dict[str, int]:
    return run_detection(db).as_dict()


@router.get("/incidents", response_model=list[IncidentRead])
def list_incidents(
    incident_status: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    service_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Incident]:
    query = (
        select(Incident)
        .options(*incident_options())
        .order_by(Incident.detected_at.desc())
        .limit(limit)
    )
    if incident_status is not None:
        query = query.where(Incident.status == incident_status)
    if severity is not None:
        query = query.where(Incident.severity == severity)
    if service_id is not None:
        query = query.where(Incident.service_id == service_id)
    return list(db.scalars(query))


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: uuid.UUID, db: Session = Depends(get_db)) -> Incident:
    incident = db.scalar(
        select(Incident).options(*incident_options()).where(Incident.id == incident_id)
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident
