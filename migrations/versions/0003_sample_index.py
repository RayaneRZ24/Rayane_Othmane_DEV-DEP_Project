"""Express replay progress as observation indices."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("replay_runs", "cursor_ms", new_column_name="cursor_index")


def downgrade():
    op.alter_column("replay_runs", "cursor_index", new_column_name="cursor_ms")
