import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.config import Settings, get_settings
from app.detection import run_detection
from app.diagnostics import (
    DiagnosisProvider,
    DiagnosisProviderError,
    DiagnosisRejectedError,
    create_diagnosis,
    get_diagnosis_provider,
)
from app.models import Incident, IncidentDiagnosis
from app.schemas import (
    DetectionRunResponse,
    DiagnosisCreate,
    IncidentDiagnosisRead,
    IncidentDetail,
    IncidentRead,
)

router = APIRouter(prefix="/api/v1", tags=["incidents"])


def incident_options():
    return (
        selectinload(Incident.service),
        selectinload(Incident.deployment),
        selectinload(Incident.evidence),
        selectinload(Incident.diagnoses),
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


@router.get(
    "/incidents/{incident_id}/diagnoses",
    response_model=list[IncidentDiagnosisRead],
)
def list_diagnoses(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[IncidentDiagnosis]:
    if db.get(Incident, incident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    query = (
        select(IncidentDiagnosis)
        .where(IncidentDiagnosis.incident_id == incident_id)
        .order_by(IncidentDiagnosis.created_at.desc())
    )
    return list(db.scalars(query))


@router.post(
    "/incidents/{incident_id}/diagnoses",
    response_model=IncidentDiagnosisRead,
    status_code=status.HTTP_201_CREATED,
)
def diagnose_incident(
    incident_id: uuid.UUID,
    payload: DiagnosisCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider: DiagnosisProvider = Depends(get_diagnosis_provider),
) -> IncidentDiagnosis:
    incident = db.scalar(
        select(Incident).options(*incident_options()).where(Incident.id == incident_id)
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    try:
        return create_diagnosis(db, incident, payload.profile, provider, settings)
    except DiagnosisRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except DiagnosisProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
