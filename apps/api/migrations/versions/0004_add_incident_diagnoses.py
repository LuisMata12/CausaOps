"""Add evidence-bound incident diagnoses."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incident_diagnoses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("conclusion", sa.String(length=30), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=False),
        sa.Column("cited_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["incident_id", "model", "status"]:
        op.create_index(
            f"ix_incident_diagnoses_{column}",
            "incident_diagnoses",
            [column],
        )


def downgrade() -> None:
    op.drop_table("incident_diagnoses")
