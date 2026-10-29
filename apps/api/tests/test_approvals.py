import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Incident, IncidentDiagnosis, Service, User
from app.security import create_token, hash_password

PASSWORD = "correct-horse-battery"


@pytest.fixture
def user(db_session: Session) -> User:
    record = User(
        email="operator@causaops.test",
        display_name="On-call operator",
        password_hash=hash_password(PASSWORD),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture
def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user.id, Settings())}"}


@pytest.fixture
def incident(db_session: Session) -> Incident:
    service = Service(name="demo-payments", environment="development")
    db_session.add(service)
    db_session.flush()
    now = datetime.now(UTC)
    record = Incident(
        service_id=service.id,
        fingerprint=f"{service.id}:service-degradation",
        title="Degradation detected in demo-payments",
        severity="high",
        status="detected",
        started_at=now,
        detected_at=now,
        event_count=6,
        summary="Deterministic rules detected a 42.9% error rate.",
        detection_context={"error_rate": 0.429},
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def _diagnosis(db: Session, incident: Incident, status: str = "completed") -> IncidentDiagnosis:
    record = IncidentDiagnosis(
        incident_id=incident.id,
        model="openai/gpt-oss-120b",
        profile="primary",
        status=status,
        prompt_snapshot={},
        cited_evidence_ids=[],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "action_type": "propose_simulated_rollback",
        "decision": "approved",
        "justification": "The timeout deployment correlates with the degradation.",
    }
    payload.update(overrides)
    return payload


def test_approval_requires_authentication(client: TestClient, incident: Incident) -> None:
    response = client.post(f"/api/v1/incidents/{incident.id}/approvals", json=_body())
    assert response.status_code == 401


def test_approving_a_rollback_records_the_decision_and_moves_the_incident(
    client: TestClient, db_session: Session, incident: Incident, user: User, auth: dict[str, str]
) -> None:
    diagnosis = _diagnosis(db_session, incident)
    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(diagnosis_id=str(diagnosis.id)),
        headers=auth,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["action_type"] == "propose_simulated_rollback"
    assert body["decision"] == "approved"
    assert body["diagnosis_id"] == str(diagnosis.id)
    assert body["decided_by_user"]["email"] == user.email
    assert body["executed_at"] is None

    db_session.expire_all()
    assert db_session.get(Incident, incident.id).status == "mitigating"


def test_rejecting_sends_the_incident_back_to_investigation(
    client: TestClient, db_session: Session, incident: Incident, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(decision="rejected", justification="Not convinced by the correlation."),
        headers=auth,
    )
    assert response.status_code == 201
    db_session.expire_all()
    assert db_session.get(Incident, incident.id).status == "investigating"


def test_arbitrary_actions_are_refused_by_the_schema(
    client: TestClient, incident: Incident, auth: dict[str, str]
) -> None:
    for action in ["rm -rf /", "DROP TABLE incidents", "https://example.com/hook", "restart"]:
        response = client.post(
            f"/api/v1/incidents/{incident.id}/approvals",
            json=_body(action_type=action),
            headers=auth,
        )
        assert response.status_code == 422


def test_resolved_incidents_refuse_a_rollback(
    client: TestClient, db_session: Session, incident: Incident, auth: dict[str, str]
) -> None:
    incident.status = "resolved"
    db_session.commit()
    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(),
        headers=auth,
    )
    assert response.status_code == 422
    assert "resolved" in response.json()["detail"]


def test_the_same_action_cannot_be_approved_twice(
    client: TestClient, incident: Incident, auth: dict[str, str]
) -> None:
    first = client.post(
        f"/api/v1/incidents/{incident.id}/approvals", json=_body(), headers=auth
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/incidents/{incident.id}/approvals", json=_body(), headers=auth
    )
    assert second.status_code == 422
    assert "awaiting execution" in second.json()["detail"]


def test_a_diagnosis_from_another_incident_is_refused(
    client: TestClient, db_session: Session, incident: Incident, auth: dict[str, str]
) -> None:
    other = Incident(
        service_id=incident.service_id,
        fingerprint="other",
        title="Other",
        severity="medium",
        status="detected",
        started_at=incident.started_at,
        detected_at=incident.detected_at,
        summary="Other incident.",
        detection_context={},
    )
    db_session.add(other)
    db_session.commit()
    foreign = _diagnosis(db_session, other)

    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(diagnosis_id=str(foreign.id)),
        headers=auth,
    )
    assert response.status_code == 422
    assert "does not belong" in response.json()["detail"]


def test_a_rejected_diagnosis_cannot_justify_an_approval(
    client: TestClient, db_session: Session, incident: Incident, auth: dict[str, str]
) -> None:
    diagnosis = _diagnosis(db_session, incident, status="rejected")
    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(diagnosis_id=str(diagnosis.id)),
        headers=auth,
    )
    assert response.status_code == 422
    assert "rejected diagnosis" in response.json()["detail"]


def test_an_unknown_diagnosis_is_refused(
    client: TestClient, incident: Incident, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(diagnosis_id=str(uuid.uuid4())),
        headers=auth,
    )
    assert response.status_code == 422


def test_unknown_incident_returns_not_found(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/incidents/{uuid.uuid4()}/approvals", json=_body(), headers=auth
    )
    assert response.status_code == 404


def test_approvals_are_listed_and_exposed_on_the_incident(
    client: TestClient, incident: Incident, auth: dict[str, str]
) -> None:
    client.post(f"/api/v1/incidents/{incident.id}/approvals", json=_body(), headers=auth)

    listed = client.get(f"/api/v1/incidents/{incident.id}/approvals")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    detail = client.get(f"/api/v1/incidents/{incident.id}")
    assert detail.status_code == 200
    assert detail.json()["approvals"][0]["action_type"] == "propose_simulated_rollback"


def test_continue_monitoring_moves_the_incident_to_monitoring(
    client: TestClient, db_session: Session, incident: Incident, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/incidents/{incident.id}/approvals",
        json=_body(action_type="continue_monitoring", justification="Watch one more window."),
        headers=auth,
    )
    assert response.status_code == 201
    db_session.expire_all()
    assert db_session.get(Incident, incident.id).status == "monitoring"


def test_the_approval_allow_list_matches_the_one_sent_to_the_model(
    db_session: Session, incident: Incident
) -> None:
    from app.approvals import allowed_actions_for
    from app.config import get_settings
    from app.diagnostics import build_prompt_snapshot

    snapshot = build_prompt_snapshot(incident, get_settings())
    assert snapshot["allowed_actions"] == allowed_actions_for(incident)

    incident.status = "resolved"
    db_session.commit()
    resolved = build_prompt_snapshot(incident, get_settings())
    assert "propose_simulated_rollback" not in resolved["allowed_actions"]
