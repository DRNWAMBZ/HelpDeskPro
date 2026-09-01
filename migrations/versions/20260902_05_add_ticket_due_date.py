"""Add ticket due dates for simple SLA tracking."""

from alembic import op
import sqlalchemy as sa

revision = "20260902_05"
down_revision = "20260901_04"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ticket")}
    if "due_at" not in columns:
        op.add_column("ticket", sa.Column("due_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("ticket", "due_at")
