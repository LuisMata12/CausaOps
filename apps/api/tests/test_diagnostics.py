from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.diagnostics import (
    DiagnosisRejectedError,
    ProviderResult,
    create_diagnosis,
    get_diagnosis_provider,
)
from app.main import app
from app.models import Incident, IncidentDiagnosis, IncidentEvidence, Service
from app.schemas import DiagnosisOutput


class FakeGroqProvider:
    name = "groq"

    def __init__(self, *, invalid_evidence: bool = False):
        self.invalid_evidence = invalid_evidence

    def generate(self, snapshot: dict, model: str) -> ProviderResult:
        evidence_id = (
            "00000000-0000-0000-0000-000000000000"
            if self.invalid_evidence
            else snapshot["evidence"][0]["evidence_id"]
        )
        output = DiagnosisOutput.model_validate(
            {
                "schema_version": "1.0",
                "conclusion": "supported",
                "summary": "La degradación coincide con los errores observados.",
                "probable_cause": {
                    "statement": "La versión desplegada presenta una regresión de timeout.",
                    "confidence": 0.86,
                    "evidence_ids": [evidence_id],
                },
                "alternative_causes": [],
                "recommended_action": {
                    "type": "propose_simulated_rollback",
                    "rationale": "La evidencia vincula los fallos con la versión desplegada.",
                    "risk": "low",
                    "evidence_ids": [evidence_id],
                },
                "missing_information": ["No hay telemetría del proveedor externo."],
            }
        )
        return ProviderResult(output=output, latency_ms=25, input_tokens=500, output_tokens=120)


def create_incident(db: Session) -> Incident:
    now = datetime.now(UTC)
    service = Service(name="diagnosis-demo", environment="test", status="operational")
    db.add(service)
    db.flush()
    incident = Incident(
        service_id=service.id,
        fingerprint=f"{service.id}:service-degradation",
        title="Degradation detected in diagnosis-demo",
        severity="high",
        status="detected",
        started_at=now,
        detected_at=now,
        event_count=1,
        summary="Deterministic rules detected a high error rate.",
        detection_context={
            "request_count": 5,
            "error_count": 5,
            "error_rate": 1.0,
            "active_rules": ["high_error_rate"],
        },
    )
    db.add(incident)
    db.flush()
    db.add(
        IncidentEvidence(
            incident_id=incident.id,
            evidence_type="telemetry_event",
            reference_id="request-error-1",
            description="Payment request timed out",
            timestamp=now,
            payload={"status_code": 504, "duration_ms": 2500},
        )
    )
    db.commit()
    db.refresh(incident)
    return incident


def test_create_evidence_bound_diagnosis(db_session: Session) -> None:
    incident = create_incident(db_session)
    diagnosis = create_diagnosis(
        db_session,
        incident,
        "test",
        FakeGroqProvider(),
        Settings(GROQ_TEST_MODEL="openai/gpt-oss-20b"),
    )

    assert diagnosis.status == "completed"
    assert diagnosis.model == "openai/gpt-oss-20b"
    assert diagnosis.confidence == 0.86
    assert diagnosis.input_tokens == 500
    assert diagnosis.response_payload["needs_human_review"] is True
    assert diagnosis.cited_evidence_ids == [str(incident.evidence[0].id)]
    assert diagnosis.prompt_snapshot["allowed_actions"] == [
        "no_action",
        "continue_monitoring",
        "propose_simulated_rollback",
    ]


def test_rejects_unknown_evidence_and_preserves_audit_record(db_session: Session) -> None:
    incident = create_incident(db_session)

    with pytest.raises(DiagnosisRejectedError, match="was not supplied"):
        create_diagnosis(
            db_session,
            incident,
            "primary",
            FakeGroqProvider(invalid_evidence=True),
            Settings(GROQ_PRIMARY_MODEL="openai/gpt-oss-120b"),
        )

    diagnosis = db_session.scalar(select(IncidentDiagnosis))
    assert diagnosis is not None
    assert diagnosis.status == "rejected"
    assert diagnosis.model == "openai/gpt-oss-120b"
    assert diagnosis.error_message is not None


def test_resolved_incident_cannot_recommend_rollback(db_session: Session) -> None:
    incident = create_incident(db_session)
    incident.status = "resolved"
    db_session.commit()

    with pytest.raises(DiagnosisRejectedError, match="not allowed"):
        create_diagnosis(
            db_session,
            incident,
            "test",
            FakeGroqProvider(),
            Settings(),
        )

    diagnosis = db_session.scalar(select(IncidentDiagnosis))
    assert diagnosis is not None
    assert diagnosis.status == "rejected"
    assert diagnosis.prompt_snapshot["allowed_actions"] == [
        "no_action",
        "continue_monitoring",
    ]


def test_diagnosis_api_creates_and_lists_results(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_incident(db_session)
    app.dependency_overrides[get_diagnosis_provider] = lambda: FakeGroqProvider()
    try:
        created = client.post(
            f"/api/v1/incidents/{incident.id}/diagnoses",
            json={"profile": "test"},
        )
        listed = client.get(f"/api/v1/incidents/{incident.id}/diagnoses")
        detail = client.get(f"/api/v1/incidents/{incident.id}")
    finally:
        app.dependency_overrides.pop(get_diagnosis_provider, None)

    assert created.status_code == 201
    assert created.json()["status"] == "completed"
    assert created.json()["provider"] == "groq"
    assert len(listed.json()) == 1
    assert len(detail.json()["diagnoses"]) == 1
