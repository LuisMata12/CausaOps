import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Incident, IncidentApproval, IncidentDiagnosis, User
from app.schemas import ApprovalCreate

#: Actions a human may approve. Remediation is always chosen from this list,
#: never supplied by a caller or a model as free text.
BASE_ACTIONS = ["no_action", "continue_monitoring"]
EXECUTABLE_ACTIONS = frozenset({"propose_simulated_rollback"})


class ApprovalRejectedError(RuntimeError):
    pass


def allowed_actions_for(incident: Incident) -> list[str]:
    """The allow-list offered to the model and enforced on approval. One source for both."""
    if incident.status == "resolved":
        return list(BASE_ACTIONS)
    return [*BASE_ACTIONS, "propose_simulated_rollback"]


def _motivating_diagnosis(
    db: Session,
    incident: Incident,
    diagnosis_id: uuid.UUID,
) -> IncidentDiagnosis:
    diagnosis = db.get(IncidentDiagnosis, diagnosis_id)
    if diagnosis is None or diagnosis.incident_id != incident.id:
        raise ApprovalRejectedError("The diagnosis does not belong to this incident")
    if diagnosis.status != "completed":
        raise ApprovalRejectedError(
            f"A {diagnosis.status} diagnosis cannot justify an approval"
        )
    return diagnosis


def _pending_execution(db: Session, incident: Incident, action_type: str) -> bool:
    return (
        db.scalar(
            select(IncidentApproval).where(
                IncidentApproval.incident_id == incident.id,
                IncidentApproval.action_type == action_type,
                IncidentApproval.decision == "approved",
                IncidentApproval.executed_at.is_(None),
            )
        )
        is not None
    )


def _status_after(incident: Incident, payload: ApprovalCreate) -> str:
    if payload.decision == "rejected":
        return "investigating"
    if payload.action_type in EXECUTABLE_ACTIONS:
        return "mitigating"
    if payload.action_type == "continue_monitoring":
        return "monitoring"
    return incident.status


def record_decision(
    db: Session,
    incident: Incident,
    user: User,
    payload: ApprovalCreate,
) -> IncidentApproval:
    """Persist one human decision and move the incident, inside the caller's transaction."""
    if incident.status == "resolved":
        raise ApprovalRejectedError("A resolved incident does not accept new approvals")
    if payload.action_type not in allowed_actions_for(incident):
        raise ApprovalRejectedError(
            f"The action {payload.action_type} is not allowed for this incident"
        )
    if payload.diagnosis_id is not None:
        _motivating_diagnosis(db, incident, payload.diagnosis_id)
    if (
        payload.decision == "approved"
        and payload.action_type in EXECUTABLE_ACTIONS
        and _pending_execution(db, incident, payload.action_type)
    ):
        raise ApprovalRejectedError(
            f"The action {payload.action_type} is already approved and awaiting execution"
        )

    approval = IncidentApproval(
        incident_id=incident.id,
        diagnosis_id=payload.diagnosis_id,
        decided_by=user.id,
        action_type=payload.action_type,
        decision=payload.decision,
        justification=payload.justification,
    )
    db.add(approval)
    incident.status = _status_after(incident, payload)
    db.commit()
    db.refresh(approval)
    return approval
