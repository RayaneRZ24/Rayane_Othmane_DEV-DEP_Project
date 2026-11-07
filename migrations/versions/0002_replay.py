"""Persist replay executions, idempotent operations and committed events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("replay_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cursor_ms", sa.BigInteger(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=False),
        sa.Column("active_slot", sa.Integer(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("replay_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False))
    op.create_table("run_events",
        sa.Column("sequence", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("replay_runs.id"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False))
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])


def downgrade():
    op.drop_table("run_events")
    op.drop_table("replay_operations")
    op.drop_table("replay_runs")
