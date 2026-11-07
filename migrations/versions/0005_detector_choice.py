"""Persist an explicit detector choice without selecting it on test scores."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("replay_runs", sa.Column("detector_name", sa.String(40), nullable=False, server_default="robust-mad-v1"))


def downgrade():
    op.drop_column("replay_runs", "detector_name")
