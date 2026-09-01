"""Add private administrator notes to tickets."""

from alembic import op
import sqlalchemy as sa


revision = "20260901_03"
down_revision = "20260901_02"
branch_labels = None
depends_on = None


def upgrade():
    if "ticket_internal_note" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "ticket_internal_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_internal_note_ticket_id",
        "ticket_internal_note",
        ["ticket_id"],
    )


def downgrade():
    op.drop_index("ix_ticket_internal_note_ticket_id", table_name="ticket_internal_note")
    op.drop_table("ticket_internal_note")
