"""Repair chat tables that may be absent in pre-migration PostgreSQL copies."""

from alembic import op
import sqlalchemy as sa


revision = "20260901_02"
down_revision = "20260901_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "chat_satisfaction_rating" not in table_names:
        op.create_table(
            "chat_satisfaction_rating",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("admin_id", sa.Integer(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["admin_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_chat_satisfaction_rating_user_id",
            "chat_satisfaction_rating",
            ["user_id"],
        )
        op.create_index(
            "ix_chat_satisfaction_rating_admin_id",
            "chat_satisfaction_rating",
            ["admin_id"],
        )

    chat_columns = {
        column["name"]
        for column in inspector.get_columns("chat_conversation")
    }
    if "resolution_requested_at" not in chat_columns:
        op.add_column(
            "chat_conversation",
            sa.Column("resolution_requested_at", sa.DateTime(), nullable=True),
        )


def downgrade():
    # This repair is intentionally non-destructive for existing deployments.
    pass
