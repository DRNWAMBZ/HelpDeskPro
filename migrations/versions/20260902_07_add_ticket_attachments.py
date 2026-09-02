"""Add private ticket attachments."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_07"
down_revision = "20260902_06"
branch_labels = None
depends_on = None


def upgrade():
    if "ticket_attachment" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "ticket_attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )
    op.create_index(
        "ix_ticket_attachment_ticket_id",
        "ticket_attachment",
        ["ticket_id"],
    )


def downgrade():
    op.drop_index("ix_ticket_attachment_ticket_id", table_name="ticket_attachment")
    op.drop_table("ticket_attachment")
