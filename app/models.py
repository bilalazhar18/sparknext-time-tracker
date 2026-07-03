from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def utc_now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Boolean, nullable=False, default=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    role = db.Column(
        db.Enum("employee", "admin", "temporary", name="user_role"),
        nullable=False,
        default="employee",
    )

    shift_assignments = db.relationship(
        "EmployeeShift",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    attendance_records = db.relationship(
        "Attendance",
        back_populates="employee",
        foreign_keys="Attendance.employee_id",
        cascade="all, delete-orphan",
    )
    covered_attendance_records = db.relationship(
        "Attendance",
        back_populates="covered_employee",
        foreign_keys="Attendance.covered_employee_id",
    )
    temporary_duties = db.relationship(
        "TemporaryDutyAssignment",
        back_populates="temporary_user",
        foreign_keys="TemporaryDutyAssignment.temporary_user_id",
        cascade="all, delete-orphan",
    )
    covered_duties = db.relationship(
        "TemporaryDutyAssignment",
        back_populates="covered_employee",
        foreign_keys="TemporaryDutyAssignment.covered_employee_id",
    )
    approved_temporary_duties = db.relationship(
        "TemporaryDutyAssignment",
        back_populates="approved_by",
        foreign_keys="TemporaryDutyAssignment.approved_by_user_id",
    )
    approved_attendance_records = db.relationship(
        "Attendance",
        back_populates="approved_by",
        foreign_keys="Attendance.approved_by_user_id",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can_login(self):
        return self.deleted_at is None and (self.status or self.role == "temporary")


class Building(TimestampMixin, db.Model):
    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    address = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Numeric(10, 7), nullable=True)
    longitude = db.Column(db.Numeric(10, 7), nullable=True)
    barcode_token = db.Column(db.String(100), nullable=False, unique=True, index=True)
    status = db.Column(db.Boolean, nullable=False, default=True)

    shifts = db.relationship(
        "Shift",
        back_populates="building",
        cascade="all, delete-orphan",
    )
    attendance_records = db.relationship("Attendance", back_populates="building")


class Shift(TimestampMixin, db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    grace_minutes = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Boolean, nullable=False, default=True)

    building = db.relationship("Building", back_populates="shifts")
    employee_assignments = db.relationship(
        "EmployeeShift",
        back_populates="shift",
        cascade="all, delete-orphan",
    )
    attendance_records = db.relationship("Attendance", back_populates="shift")

    __table_args__ = (
        db.UniqueConstraint("building_id", "name", name="uq_shift_building_name"),
    )


class EmployeeShift(TimestampMixin, db.Model):
    __tablename__ = "employee_shifts"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    status = db.Column(db.Boolean, nullable=False, default=True)

    employee = db.relationship("User", back_populates="shift_assignments")
    shift = db.relationship("Shift", back_populates="employee_assignments")

    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "shift_id",
            "effective_from",
            name="uq_employee_shift_effective_from",
        ),
    )


class Attendance(TimestampMixin, db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    covered_employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    temporary_duty_id = db.Column(
        db.Integer,
        db.ForeignKey("temporary_duty_assignments.id"),
        nullable=True,
    )
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)
    attendance_date = db.Column(db.Date, nullable=False)
    check_in_at = db.Column(db.DateTime, nullable=True)
    check_out_at = db.Column(db.DateTime, nullable=True)
    timezone_name = db.Column(db.String(64), nullable=False, default="Asia/Karachi")
    timezone_offset_minutes = db.Column(db.Integer, nullable=False, default=300)
    check_in_status = db.Column(
        db.Enum("on_time", "late", "early", name="check_in_status"),
        nullable=True,
    )
    check_out_status = db.Column(
        db.Enum("on_time", "early", "overtime", name="check_out_status"),
        nullable=True,
    )
    source = db.Column(
        db.Enum("barcode", "manual", name="attendance_source"),
        nullable=False,
        default="barcode",
    )
    approval_status = db.Column(
        db.Enum("pending", "approved", "rejected", name="attendance_approval_status"),
        nullable=False,
        default="approved",
    )
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(255), nullable=True)

    employee = db.relationship(
        "User",
        back_populates="attendance_records",
        foreign_keys=[employee_id],
    )
    covered_employee = db.relationship(
        "User",
        back_populates="covered_attendance_records",
        foreign_keys=[covered_employee_id],
    )
    approved_by = db.relationship(
        "User",
        back_populates="approved_attendance_records",
        foreign_keys=[approved_by_user_id],
    )
    temporary_duty = db.relationship(
        "TemporaryDutyAssignment",
        back_populates="attendance_records",
    )
    building = db.relationship("Building", back_populates="attendance_records")
    shift = db.relationship("Shift", back_populates="attendance_records")

    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "attendance_date",
            "shift_id",
            name="uq_attendance_employee_date_shift",
        ),
    )


class TemporaryDutyAssignment(TimestampMixin, db.Model):
    __tablename__ = "temporary_duty_assignments"

    id = db.Column(db.Integer, primary_key=True)
    temporary_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    covered_employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)
    duty_date = db.Column(db.Date, nullable=False)
    status = db.Column(
        db.Enum("pending", "approved", "rejected", "completed", name="temporary_duty_status"),
        nullable=False,
        default="pending",
    )
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(255), nullable=True)

    temporary_user = db.relationship(
        "User",
        back_populates="temporary_duties",
        foreign_keys=[temporary_user_id],
    )
    covered_employee = db.relationship(
        "User",
        back_populates="covered_duties",
        foreign_keys=[covered_employee_id],
    )
    approved_by = db.relationship(
        "User",
        back_populates="approved_temporary_duties",
        foreign_keys=[approved_by_user_id],
    )
    building = db.relationship("Building")
    shift = db.relationship("Shift")
    attendance_records = db.relationship(
        "Attendance",
        back_populates="temporary_duty",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "temporary_user_id",
            "duty_date",
            "shift_id",
            name="uq_temporary_duty_user_date_shift",
        ),
    )
