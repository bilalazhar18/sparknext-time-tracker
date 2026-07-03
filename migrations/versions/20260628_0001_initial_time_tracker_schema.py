"""initial time tracker schema

Revision ID: 20260628_0001
Revises: 
Create Date: 2026-06-28 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260628_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    current_timestamp = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "role",
            sa.Enum("employee", "admin", "temporary", name="user_role"),
            nullable=False,
            server_default="employee",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "buildings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("barcode_token", sa.String(length=100), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_buildings_code"), "buildings", ["code"], unique=True)
    op.create_index(
        op.f("ix_buildings_barcode_token"),
        "buildings",
        ["barcode_token"],
        unique=True,
    )

    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.ForeignKeyConstraint(["building_id"], ["buildings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("building_id", "name", name="uq_shift_building_name"),
    )

    op.create_table(
        "employee_shifts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "shift_id",
            "effective_from",
            name="uq_employee_shift_effective_from",
        ),
    )

    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("check_in_at", sa.DateTime(), nullable=True),
        sa.Column("check_out_at", sa.DateTime(), nullable=True),
        sa.Column(
            "timezone_name",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Karachi",
        ),
        sa.Column(
            "timezone_offset_minutes",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
        sa.Column(
            "check_in_status",
            sa.Enum("on_time", "late", "early", name="check_in_status"),
            nullable=True,
        ),
        sa.Column(
            "check_out_status",
            sa.Enum("on_time", "early", "overtime", name="check_out_status"),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.Enum("barcode", "manual", name="attendance_source"),
            nullable=False,
            server_default="barcode",
        ),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=current_timestamp),
        sa.ForeignKeyConstraint(["building_id"], ["buildings.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "attendance_date",
            "shift_id",
            name="uq_attendance_employee_date_shift",
        ),
    )


def downgrade():
    op.drop_table("attendance")
    op.drop_table("employee_shifts")
    op.drop_table("shifts")
    op.drop_index(op.f("ix_buildings_barcode_token"), table_name="buildings")
    op.drop_index(op.f("ix_buildings_code"), table_name="buildings")
    op.drop_table("buildings")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
