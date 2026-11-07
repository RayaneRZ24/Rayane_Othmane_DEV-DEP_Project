"""Persist training references, analysis state and evidence-backed alerts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("replay_runs", sa.Column("detector_profile", postgresql.JSONB(), nullable=True))
    op.add_column("replay_runs", sa.Column("detector_state", postgresql.JSONB(), nullable=True))
    op.add_column("replay_runs", sa.Column("analyzed_index", sa.BigInteger(), nullable=True))
    op.create_table("alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("replay_runs.id"), nullable=False),
        sa.Column("feature_id", sa.String(100), nullable=False),
        sa.Column("feature_label", sa.String(150), nullable=False),
        sa.Column("resource", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_index", sa.BigInteger(), nullable=False),
        sa.Column("detected_index", sa.BigInteger(), nullable=False),
        sa.Column("last_anomalous_index", sa.BigInteger(), nullable=False),
        sa.Column("closed_index", sa.BigInteger(), nullable=True),
        sa.Column("peak_score", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("run_id", "feature_id", "detected_index", name="uq_alert_detection"))
    op.create_index("ix_alerts_run_id", "alerts", ["run_id"])


def downgrade():
    op.drop_table("alerts")
    op.drop_column("replay_runs", "analyzed_index")
    op.drop_column("replay_runs", "detector_state")
    op.drop_column("replay_runs", "detector_profile")
