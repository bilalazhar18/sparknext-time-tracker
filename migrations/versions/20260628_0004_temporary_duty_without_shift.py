"""temporary duty without assigned shift

Revision ID: 20260628_0004
Revises: 20260628_0003
Create Date: 2026-06-28 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260628_0004"
down_revision = "20260628_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "temporary_duty_assignments",
        "shift_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "temporary_duty_assignments",
        "shift_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
