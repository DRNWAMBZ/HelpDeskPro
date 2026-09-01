"""Add ticket status audit history."""
from alembic import op
import sqlalchemy as sa

revision = "20260902_06"
down_revision = "20260902_05"
branch_labels = None
depends_on = None

def upgrade():
    if "ticket_status_history" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table("ticket_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=False),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.ForeignKeyConstraint(["changed_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_ticket_status_history_ticket_id", "ticket_status_history", ["ticket_id"])

def downgrade():
    op.drop_index("ix_ticket_status_history_ticket_id", table_name="ticket_status_history")
    op.drop_table("ticket_status_history")
