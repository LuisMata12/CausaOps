import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LiveResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["reachable"]


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    environment: str = Field(default="development", min_length=1, max_length=40)


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    environment: str
    status: str
    created_at: datetime


class TelemetryEventCreate(BaseModel):
    service_id: uuid.UUID
    event_type: Literal["log", "request", "health_check"]
    level: Literal["debug", "info", "warning", "error", "critical"]
    message: str = Field(min_length=1, max_length=4000)
    timestamp: datetime
    trace_id: str | None = Field(default=None, max_length=64)
    version: str | None = Field(default=None, max_length=60)
    duration_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelemetryEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    event_type: str
    level: str
    message: str
    timestamp: datetime
    trace_id: str | None
    version: str | None
    duration_ms: int | None
    attributes: dict[str, Any] = Field(serialization_alias="metadata")


class MetricSampleCreate(BaseModel):
    service_id: uuid.UUID
    metric_name: str = Field(min_length=1, max_length=120)
    value: float
    timestamp: datetime
    labels: dict[str, str] = Field(default_factory=dict)


class MetricSampleRead(MetricSampleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class DeploymentCreate(BaseModel):
    service_id: uuid.UUID
    version: str = Field(min_length=1, max_length=60)
    commit_sha: str = Field(min_length=7, max_length=64)
    timestamp: datetime
    status: Literal["succeeded", "failed", "rolled_back"]
    changed_files: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    version: str
    commit_sha: str
    timestamp: datetime
    status: str
    changed_files: list[str]
    attributes: dict[str, Any] = Field(serialization_alias="metadata")


class IncidentEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_type: str
    reference_id: str
    description: str
    timestamp: datetime
    payload: dict[str, Any]


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    deployment_id: uuid.UUID | None
    fingerprint: str
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    status: Literal[
        "detected",
        "investigating",
        "awaiting_approval",
        "mitigating",
        "monitoring",
        "resolved",
        "rejected",
    ]
    started_at: datetime
    detected_at: datetime
    resolved_at: datetime | None
    event_count: int
    summary: str
    detection_context: dict[str, Any]
    service: ServiceRead
    deployment: DeploymentRead | None


class IncidentDetail(IncidentRead):
    evidence: list[IncidentEvidenceRead]


class DetectionRunResponse(BaseModel):
    services_checked: int
    incidents_created: int
    incidents_updated: int
    incidents_resolved: int
