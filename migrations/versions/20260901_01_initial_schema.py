"""Create the HelpDesk Pro schema from the SQLAlchemy metadata."""

from alembic import op


revision = "20260901_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from app import db

    db.metadata.create_all(bind=op.get_bind())


def downgrade():
    from app import db

    db.metadata.drop_all(bind=op.get_bind())
