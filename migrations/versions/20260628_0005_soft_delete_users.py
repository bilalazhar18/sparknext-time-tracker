"""soft delete users

Revision ID: 20260628_0005
Revises: 20260628_0004
Create Date: 2026-06-28 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260628_0005"
down_revision = "20260628_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("users", "deleted_at")
