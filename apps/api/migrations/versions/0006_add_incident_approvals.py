"""Add human approvals for allow-listed incident actions."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incident_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("diagnosis_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_status", sa.String(length=30), nullable=True),
        sa.Column("execution_detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["incident_diagnoses.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["incident_id", "decided_by", "action_type", "decision"]:
        op.create_index(
            f"ix_incident_approvals_{column}",
            "incident_approvals",
            [column],
        )


def downgrade() -> None:
    op.drop_table("incident_approvals")
