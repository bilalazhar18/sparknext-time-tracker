"""temporary duty flow

Revision ID: 20260628_0002
Revises: 20260628_0001
Create Date: 2026-06-28 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260628_0002"
down_revision = "20260628_0001"
branch_labels = None
depends_on = None


def upgrade():
    current_timestamp = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "temporary_duty_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("temporary_user_id", sa.Integer(), nullable=False),
        sa.Column("covered_employee_id", sa.Integer(), nullable=True),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("duty_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "completed", name="temporary_duty_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.ForeignKeyConstraint(
            ["temporary_user_id"],
            ["users.id"],
            name="fk_temporary_duty_temporary_user",
        ),
        sa.ForeignKeyConstraint(
            ["covered_employee_id"],
            ["users.id"],
            name="fk_temporary_duty_covered_employee",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name="fk_temporary_duty_approved_by",
        ),
        sa.ForeignKeyConstraint(
            ["building_id"],
            ["buildings.id"],
            name="fk_temporary_duty_building",
        ),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
            name="fk_temporary_duty_shift",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "temporary_user_id",
            "duty_date",
            "shift_id",
            name="uq_temporary_duty_user_date_shift",
        ),
    )

    op.add_column(
        "attendance",
        sa.Column("covered_employee_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "attendance",
        sa.Column("temporary_duty_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "attendance",
        sa.Column(
            "approval_status",
            sa.Enum("pending", "approved", "rejected", name="attendance_approval_status"),
            nullable=False,
            server_default="approved",
        ),
    )
    op.create_foreign_key(
        "fk_attendance_covered_employee",
        "attendance",
        "users",
        ["covered_employee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_attendance_temporary_duty",
        "attendance",
        "temporary_duty_assignments",
        ["temporary_duty_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_attendance_temporary_duty", "attendance", type_="foreignkey")
    op.drop_constraint("fk_attendance_covered_employee", "attendance", type_="foreignkey")
    op.drop_column("attendance", "approval_status")
    op.drop_column("attendance", "temporary_duty_id")
    op.drop_column("attendance", "covered_employee_id")
    op.drop_table("temporary_duty_assignments")
