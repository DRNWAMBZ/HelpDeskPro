"""Add private ticket tags."""

from alembic import op
import sqlalchemy as sa

revision = "20260901_04"
down_revision = "20260901_03"
branch_labels = None
depends_on = None


def upgrade():
    if "ticket_tag" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "ticket_tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "name", name="uq_ticket_tag_name"),
    )
    op.create_index("ix_ticket_tag_ticket_id", "ticket_tag", ["ticket_id"])


def downgrade():
    op.drop_index("ix_ticket_tag_ticket_id", table_name="ticket_tag")
    op.drop_table("ticket_tag")
