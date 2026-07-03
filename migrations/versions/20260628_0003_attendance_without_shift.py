"""attendance without assigned shift

Revision ID: 20260628_0003
Revises: 20260628_0002
Create Date: 2026-06-28 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260628_0003"
down_revision = "20260628_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "attendance",
        "shift_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "attendance",
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "attendance",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        "fk_attendance_approved_by",
        "attendance",
        "users",
        ["approved_by_user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_attendance_approved_by", "attendance", type_="foreignkey")
    op.drop_column("attendance", "approved_at")
    op.drop_column("attendance", "approved_by_user_id")
    op.alter_column(
        "attendance",
        "shift_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
