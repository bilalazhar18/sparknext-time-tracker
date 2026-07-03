"""
Time tracker database seeder.

Run:
    .\\venv\\Scripts\\python.exe seeder.py
"""

from datetime import datetime, time, timedelta, timezone

from app import db
from app.models import Attendance, Building, EmployeeShift, Shift, User
from run import app


APP_TZ = timezone(timedelta(hours=5), "Asia/Karachi")


def local_to_utc_naive(day, clock_time):
    local_dt = datetime.combine(day, clock_time, tzinfo=APP_TZ)
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


def get_or_create_user(name, email, password, role="employee", status=True):
    user = User.query.filter_by(email=email).first()
    if user:
        return user, False

    user = User(name=name, email=email, role=role, status=status)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user, True


def get_or_create_building(name, code, address, latitude, longitude, barcode_token):
    building = Building.query.filter_by(code=code).first()
    if building:
        return building, False

    building = Building(
        name=name,
        code=code,
        address=address,
        latitude=latitude,
        longitude=longitude,
        barcode_token=barcode_token,
        status=True,
    )
    db.session.add(building)
    db.session.flush()
    return building, True


def get_or_create_shift(building, name, start_time, end_time, grace_minutes=10):
    shift = Shift.query.filter_by(building_id=building.id, name=name).first()
    if shift:
        return shift, False

    shift = Shift(
        building_id=building.id,
        name=name,
        start_time=start_time,
        end_time=end_time,
        grace_minutes=grace_minutes,
        status=True,
    )
    db.session.add(shift)
    db.session.flush()
    return shift, True


def assign_shift(employee, shift, effective_from):
    assignment = EmployeeShift.query.filter_by(
        employee_id=employee.id,
        shift_id=shift.id,
        effective_from=effective_from,
    ).first()
    if assignment:
        return assignment, False

    assignment = EmployeeShift(
        employee_id=employee.id,
        shift_id=shift.id,
        effective_from=effective_from,
        status=True,
    )
    db.session.add(assignment)
    db.session.flush()
    return assignment, True


def create_attendance(employee, building, shift, attendance_date, check_in, check_out, check_in_status, check_out_status):
    attendance = Attendance.query.filter_by(
        employee_id=employee.id,
        attendance_date=attendance_date,
        shift_id=shift.id,
    ).first()
    if attendance:
        return attendance, False

    attendance = Attendance(
        employee_id=employee.id,
        building_id=building.id,
        shift_id=shift.id,
        attendance_date=attendance_date,
        check_in_at=local_to_utc_naive(attendance_date, check_in),
        check_out_at=local_to_utc_naive(attendance_date, check_out) if check_out else None,
        timezone_name="Asia/Karachi",
        timezone_offset_minutes=300,
        check_in_status=check_in_status,
        check_out_status=check_out_status,
        source="barcode",
    )
    db.session.add(attendance)
    db.session.flush()
    return attendance, True


def run():
    with app.app_context():
        print("\n[SEEDER] Seeding time tracker data...\n")

        try:
            created = {
                "users": 0,
                "buildings": 0,
                "shifts": 0,
                "assignments": 0,
                "attendance": 0,
            }

            admin, was_created = get_or_create_user(
                "System Admin",
                "admin@timetracker.com",
                "admin123",
                role="admin",
            )
            created["users"] += int(was_created)

            ali, was_created = get_or_create_user(
                "Ali Khan",
                "ali@timetracker.com",
                "employee123",
                role="employee",
            )
            created["users"] += int(was_created)

            sara, was_created = get_or_create_user(
                "Sara Ahmed",
                "sara@timetracker.com",
                "employee123",
                role="employee",
            )
            created["users"] += int(was_created)

            temp, was_created = get_or_create_user(
                "Temporary User",
                "temp@timetracker.com",
                "temp123",
                role="temporary",
            )
            created["users"] += int(was_created)

            hq, was_created = get_or_create_building(
                "Head Office",
                "HQ",
                "Main Boulevard, Lahore",
                31.5204000,
                74.3587000,
                "building-hq-main",
            )
            created["buildings"] += int(was_created)

            warehouse, was_created = get_or_create_building(
                "Warehouse",
                "WH",
                "Industrial Area, Lahore",
                31.4504000,
                74.2850000,
                "building-wh-industrial",
            )
            created["buildings"] += int(was_created)

            hq_morning, was_created = get_or_create_shift(hq, "Morning Shift", time(9, 0), time(17, 0), 10)
            created["shifts"] += int(was_created)

            hq_evening, was_created = get_or_create_shift(hq, "Evening Shift", time(14, 0), time(22, 0), 10)
            created["shifts"] += int(was_created)

            wh_morning, was_created = get_or_create_shift(warehouse, "Warehouse Morning", time(8, 0), time(16, 0), 15)
            created["shifts"] += int(was_created)

            today = datetime.now(APP_TZ).date()
            first_day = today - timedelta(days=7)

            for employee, shift in ((ali, hq_morning), (sara, hq_evening), (temp, wh_morning)):
                _, was_created = assign_shift(employee, shift, first_day)
                created["assignments"] += int(was_created)

            samples = [
                (ali, hq, hq_morning, today, time(8, 58), time(17, 3), "on_time", "on_time"),
                (sara, hq, hq_evening, today, time(14, 12), None, "late", None),
                (temp, warehouse, wh_morning, today - timedelta(days=1), time(7, 55), time(16, 20), "on_time", "overtime"),
            ]

            for sample in samples:
                _, was_created = create_attendance(*sample)
                created["attendance"] += int(was_created)

            db.session.commit()

            print("[OK] Seed complete.")
            print("[Created]")
            for key, value in created.items():
                print(f"  {key}: {value}")

            print("\n[Totals]")
            print(f"  users: {User.query.count()}")
            print(f"  buildings: {Building.query.count()}")
            print(f"  shifts: {Shift.query.count()}")
            print(f"  employee_shifts: {EmployeeShift.query.count()}")
            print(f"  attendance: {Attendance.query.count()}")

            print("\n[Login test users]")
            print("  admin@timetracker.com / admin123")
            print("  ali@timetracker.com / employee123")
            print("  sara@timetracker.com / employee123")
            print("  temp@timetracker.com / temp123")
            print()

        except Exception as exc:
            db.session.rollback()
            print(f"[ERROR] Seeding failed: {exc}")
            raise


if __name__ == "__main__":
    run()
