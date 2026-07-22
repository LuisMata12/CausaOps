"""Add incidents and evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detection_context", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("reference_id", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incident_id",
            "evidence_type",
            "reference_id",
            name="uq_incident_evidence_reference",
        ),
    )
    for column in ["service_id", "fingerprint", "severity", "status", "started_at", "detected_at"]:
        op.create_index(f"ix_incidents_{column}", "incidents", [column])
    for column in ["incident_id", "evidence_type", "timestamp"]:
        op.create_index(f"ix_incident_evidence_{column}", "incident_evidence", [column])


def downgrade() -> None:
    op.drop_table("incident_evidence")
    op.drop_table("incidents")
