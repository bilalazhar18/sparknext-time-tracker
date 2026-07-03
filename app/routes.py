from datetime import date, datetime, timedelta, timezone
import uuid
from math import atan2, cos, radians, sin, sqrt

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for, session
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import Attendance, Building, EmployeeShift, Shift, TemporaryDutyAssignment, User

main = Blueprint("main", __name__)
APP_TZ = timezone(timedelta(hours=5), "Asia/Karachi")


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now():
    return datetime.now(APP_TZ)


def local_today():
    return local_now().date()


def as_local_datetime(value):
    if not value:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(APP_TZ)


def format_local_time(value):
    local_value = as_local_datetime(value)
    if not local_value:
        return "-"

    return local_value.strftime("%I:%M %p")


def attendance_total_time(attendance, require_approval=True):
    if require_approval and attendance.approval_status != "approved":
        return "--"

    if not attendance.check_in_at or not attendance.check_out_at:
        return "--"

    total_seconds = int((attendance.check_out_at - attendance.check_in_at).total_seconds())
    if total_seconds < 0:
        return "--"

    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m"


def active_shift_assignment(user):
    today = local_today()
    return (
        EmployeeShift.query.join(Shift)
        .filter(
            EmployeeShift.employee_id == user.id,
            EmployeeShift.status.is_(True),
            EmployeeShift.effective_from <= today,
            (EmployeeShift.effective_to.is_(None)) | (EmployeeShift.effective_to >= today),
        )
        .order_by(EmployeeShift.effective_from.desc())
        .first()
    )


def distance_in_meters(lat1, lng1, lat2, lng2):
    earth_radius_meters = 6371000
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return earth_radius_meters * (2 * atan2(sqrt(a), sqrt(1 - a)))


def active_employee_building(user):
    assignment = active_shift_assignment(user)

    if assignment and assignment.shift and assignment.shift.building:
        return assignment.shift.building

    return Building.query.filter_by(status=True).order_by(Building.id.asc()).first()


def building_payload(building, distance_meters=None):
    return {
        "id": building.id,
        "name": building.name,
        "address": building.address,
        "latitude": float(building.latitude) if building.latitude is not None else None,
        "longitude": float(building.longitude) if building.longitude is not None else None,
        "distance_meters": round(distance_meters) if distance_meters is not None else None,
    }


def attendance_payload(attendance):
    return {
        "id": attendance.id,
        "approval_status": attendance.approval_status,
        "check_in_at": attendance.check_in_at.isoformat() if attendance.check_in_at else None,
        "check_out_at": attendance.check_out_at.isoformat() if attendance.check_out_at else None,
        "building": attendance.building.name if attendance.building else None,
        "shift": attendance.shift.name if attendance.shift else None,
    }


def today_attendance_for(user):
    today = local_today()
    return (
        Attendance.query.filter(
            Attendance.employee_id == user.id,
            Attendance.attendance_date == today,
        )
        .order_by(Attendance.id.desc())
        .first()
    )


def open_attendance_for(user):
    today = local_today()
    return (
        Attendance.query.filter(
            Attendance.employee_id == user.id,
            Attendance.attendance_date == today,
            Attendance.check_in_at.isnot(None),
            Attendance.check_out_at.is_(None),
        )
        .order_by(Attendance.id.desc())
        .first()
    )


def check_in_status_for(shift, now_local):
    if not shift:
        return None

    shift_start = datetime.combine(now_local.date(), shift.start_time, tzinfo=APP_TZ)
    grace_limit = shift_start.replace()
    if shift.grace_minutes:
        grace_limit = shift_start + timedelta(minutes=shift.grace_minutes)

    if now_local < shift_start:
        return "early"
    if now_local <= grace_limit:
        return "on_time"
    return "late"


def check_out_status_for(shift, now_local):
    if not shift:
        return None

    shift_end = datetime.combine(now_local.date(), shift.end_time, tzinfo=APP_TZ)
    if shift.end_time <= shift.start_time:
        shift_end = shift_end + timedelta(days=1)

    if now_local < shift_end:
        return "early"
    if now_local == shift_end:
        return "on_time"
    return "overtime"


def building_from_request(payload):
    building_id = payload.get("building_id")
    if building_id:
        building = Building.query.filter_by(id=building_id, status=True).first()
        if building:
            return building

    return active_employee_building(current_user)


def admin_dashboard_cards():
    active_staff = User.query.filter(
        User.role.in_(["employee", "temporary"]),
        User.deleted_at.is_(None),
        User.status.is_(True),
    )
    registered_staff = User.query.filter(
        User.role.in_(["employee", "temporary"]),
        User.deleted_at.is_(None),
    )

    return [
        {
            "label": "Registered Staff",
            "value": registered_staff.count(),
            "class": "bg-danger",
            "icon": "flaticon-381-user-7",
        },
        {
            "label": "Active Staff",
            "value": active_staff.count(),
            "class": "bg-success",
            "icon": "flaticon-381-user-9",
        },
        {
            "label": "Active Shifts",
            "value": Shift.query.filter(Shift.status.is_(True)).count(),
            "class": "bg-info",
            "icon": "flaticon-381-calendar-1",
        },
        {
            "label": "Pending Approvals",
            "value": Attendance.query.filter(Attendance.approval_status == "pending").count(),
            "class": "bg-secondary",
            "icon": "flaticon-381-clock",
        },
    ]


def employee_dashboard_cards(user):
    attendance_records = Attendance.query.filter(Attendance.employee_id == user.id)

    return [
        {
            "label": "Total Attendance",
            "value": attendance_records.count(),
            "class": "bg-danger",
            "icon": "flaticon-381-calendar-1",
        },
        {
            "label": "Approved Logs",
            "value": attendance_records.filter(Attendance.approval_status == "approved").count(),
            "class": "bg-success",
            "icon": "flaticon-381-success",
        },
        {
            "label": "Pending Logs",
            "value": attendance_records.filter(Attendance.approval_status == "pending").count(),
            "class": "bg-info",
            "icon": "flaticon-381-clock",
        },
        {
            "label": "Completed Duties",
            "value": attendance_records.filter(Attendance.check_out_at.isnot(None)).count(),
            "class": "bg-secondary",
            "icon": "flaticon-381-stopwatch",
        },
    ]


@main.route("/register/<barcode_token>")
def scan_barcode(barcode_token):
    building = Building.query.filter_by(barcode_token=barcode_token, status=True).first()
    if not building:
        flash("Invalid or inactive barcode.", "danger")
        return redirect(url_for("main.login"))
        
    session["scanned_building_id"] = building.id
    session["scanned_building_name"] = building.name
    flash(f"Location detected: {building.name}. Please register or sign in to mark attendance.", "info")
    return redirect(url_for("main.register"))


@main.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    
    buildings = Building.query.filter_by(status=True).all()
    if not buildings:
        return redirect(url_for("main.login"))
        
    return render_template("authentication/kiosk.html", buildings=buildings)


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    errors = {}
    email = ""

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user:
            errors["email"] = "No account found with this email."
        elif not user.check_password(password):
            errors["password"] = "Password is incorrect."
        elif not user.can_login():
            errors["email"] = "This account is inactive. Please contact admin."
        else:
            if user.role != "admin":
                try:
                    lat = float(request.form.get("latitude"))
                    lng = float(request.form.get("longitude"))
                except (TypeError, ValueError):
                    errors["email"] = "Location is required to log in."
                else:
                    buildings = Building.query.filter_by(status=True).all()
                    in_range = False
                    for b in buildings:
                        if b.latitude and b.longitude:
                            dist = distance_in_meters(lat, lng, float(b.latitude), float(b.longitude))
                            if dist <= 50:
                                in_range = True
                                break
                    if not in_range:
                        errors["email"] = "You must be within 50 meters of a building premises to log in."
            
            if not errors:
                login_user(user)
                return redirect(url_for("main.home"))

    return render_template("authentication/login.html", errors=errors, email=email)


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if not session.get("scanned_building_id"):
        flash("New users must scan a building's QR code to register.", "danger")
        return redirect(url_for("main.login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return render_template("authentication/register.html")

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return render_template("authentication/register.html")

        scanned_building_id = session.get("scanned_building_id")
        if scanned_building_id:
            building = Building.query.get(scanned_building_id)
            if building and building.latitude and building.longitude:
                try:
                    latitude = float(request.form.get("latitude"))
                    longitude = float(request.form.get("longitude"))
                    distance = distance_in_meters(latitude, longitude, float(building.latitude), float(building.longitude))
                    if distance > 100:
                        flash(f"Location mismatch: Your phone is reporting you are {int(distance)} meters away. (Phone GPS: {latitude}, {longitude})", "danger")
                        return render_template("authentication/register.html")
                except (TypeError, ValueError):
                    flash("Location is required to sign up for this building.", "danger")
                    return render_template("authentication/register.html")

        user = User(name=name, email=email, role="temporary", status=False)
        user.set_password(password)

        from app import db

        db.session.add(user)
        db.session.commit()

        flash("Account created. Please sign in.", "success")
        return redirect(url_for("main.login"))

    return render_template("authentication/register.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


@main.route("/dashboard")
@login_required
def home():
    scanned_building_id = session.get("scanned_building_id")
    current_building = None
    if scanned_building_id:
        current_building = Building.query.filter_by(id=scanned_building_id, status=True).first()
    
    if not current_building:
        current_building = active_employee_building(current_user)
    today_attendance = None
    try:
        today_attendance = today_attendance_for(current_user)
    except SQLAlchemyError:
        db.session.rollback()

    dashboard_cards = (
        admin_dashboard_cards()
        if current_user.role == "admin"
        else employee_dashboard_cards(current_user)
    )
    dashboard_heading = "Admin Dashboard" if current_user.role == "admin" else "Employee Dashboard"

    buildings = []
    if current_user.role == "admin":
        buildings = Building.query.filter_by(status=True).all()

    return render_template(
        "index.html",
        dashboard_cards=dashboard_cards,
        current_building=current_building,
        current_location_name=current_building.name if current_building else "your location",
        today_attendance=today_attendance,
        page_heading=dashboard_heading,
        buildings=buildings,
    )


@main.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        password = request.form.get("password")
        if password:
            current_user.set_password(password)
            db.session.commit()
            flash("Password updated successfully.", "success")
        else:
            flash("Please enter a new password to update.", "danger")
        return redirect(url_for("main.profile"))

    return render_template(
        "employee/profile.html",
        page_heading="My Profile"
    )

@main.route("/employees")
@login_required
def employee_list():
    employees = (
        User.query.filter(
            User.role.in_(["employee", "temporary"]),
            User.deleted_at.is_(None),
        )
        .order_by(User.created_at.desc(), User.name.asc())
        .all()
    )
    return render_template(
        "employee/list.html",
        employees=employees,
        errors={},
        form_data={
            "name": "",
            "email": "",
            "role": "employee",
            "status": "1",
        },
        open_staff_modal=False,
        page_heading="Employees",
    )


@main.route("/employees/create", methods=["GET", "POST"])
@login_required
def employee_create():
    if current_user.role != "admin":
        flash("Only admin users can add staff.", "danger")
        return redirect(url_for("main.employee_list"))

    errors = {}
    form_data = {
        "name": "",
        "email": "",
        "role": "employee",
        "status": "1",
    }

    if request.method == "POST":
        form_data = {
            "name": (request.form.get("name") or "").strip(),
            "email": (request.form.get("email") or "").strip().lower(),
            "role": request.form.get("role") or "employee",
            "status": request.form.get("status") or "1",
        }
        password = request.form.get("password") or ""

        if not form_data["name"]:
            errors["name"] = "Name is required."
        if not form_data["email"]:
            errors["email"] = "Email is required."
        elif User.query.filter_by(email=form_data["email"]).first():
            errors["email"] = "This email is already registered."
        if not password:
            errors["password"] = "Password is required."
        if form_data["role"] not in {"employee", "temporary"}:
            form_data["role"] = "employee"

        if not errors:
            user = User(
                name=form_data["name"],
                email=form_data["email"],
                role=form_data["role"],
                status=form_data["status"] == "1",
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Staff member added successfully.", "success")
            return redirect(url_for("main.employee_list"))

        employees = (
            User.query.filter(
                User.role.in_(["employee", "temporary"]),
                User.deleted_at.is_(None),
            )
            .order_by(User.created_at.desc(), User.name.asc())
            .all()
        )
        return render_template(
            "employee/list.html",
            employees=employees,
            errors=errors,
            form_data=form_data,
            open_staff_modal=True,
            page_heading="Employees",
        )

    return render_template(
        "employee/form.html",
        errors=errors,
        form_data=form_data,
        page_heading="Add Staff",
    )


@main.route("/employees/<int:user_id>/edit", methods=["POST"])
@login_required
def employee_update(user_id):
    if current_user.role != "admin":
        flash("Only admin users can edit staff.", "danger")
        return redirect(url_for("main.employee_list"))

    employee = User.query.filter(
        User.id == user_id,
        User.role.in_(["employee", "temporary"]),
        User.deleted_at.is_(None),
    ).first_or_404()

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    role = request.form.get("role") or "employee"
    status = request.form.get("status") or "1"
    password = request.form.get("password") or ""

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("main.employee_list"))

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for("main.employee_list"))

    existing_user = User.query.filter(User.email == email, User.id != employee.id).first()
    if existing_user:
        flash("This email is already registered.", "danger")
        return redirect(url_for("main.employee_list"))

    if role not in {"employee", "temporary"}:
        role = "employee"

    employee.name = name
    employee.email = email
    employee.role = role
    employee.status = status == "1"
    if password:
        employee.set_password(password)

    db.session.commit()
    flash("Staff member updated successfully.", "success")
    return redirect(url_for("main.employee_list"))


@main.route("/employees/<int:user_id>/delete", methods=["POST"])
@login_required
def employee_delete(user_id):
    if current_user.role != "admin":
        flash("Only admin users can delete staff.", "danger")
        return redirect(url_for("main.employee_list"))

    employee = User.query.filter(
        User.id == user_id,
        User.role.in_(["employee", "temporary"]),
        User.deleted_at.is_(None),
    ).first_or_404()

    employee.status = False
    employee.deleted_at = utc_now_naive()
    db.session.commit()

    flash("Staff member deleted successfully.", "success")
    return redirect(url_for("main.employee_list"))


@main.route("/buildings")
@login_required
def building_list():
    if current_user.role != "admin":
        flash("Only admin users can view buildings.", "danger")
        return redirect(url_for("main.home"))

    buildings = Building.query.order_by(Building.created_at.desc()).all()
    return render_template(
        "building/list.html",
        buildings=buildings,
        errors={},
        form_data={
            "name": "",
            "code": "",
            "address": "",
            "latitude": "",
            "longitude": "",
            "status": "1",
            "add_shifts": "0"
        },
        open_modal=False,
        page_heading="Buildings",
    )


@main.route("/buildings/create", methods=["GET", "POST"])
@login_required
def building_create():
    if current_user.role != "admin":
        flash("Only admin users can add buildings.", "danger")
        return redirect(url_for("main.building_list"))

    errors = {}
    form_data = {
        "name": "",
        "code": "",
        "address": "",
        "latitude": "",
        "longitude": "",
        "status": "1",
        "add_shifts": "0"
    }

    if request.method == "POST":
        form_data = {
            "name": (request.form.get("name") or "").strip(),
            "code": (request.form.get("code") or "").strip(),
            "address": (request.form.get("address") or "").strip(),
            "latitude": (request.form.get("latitude") or "").strip(),
            "longitude": (request.form.get("longitude") or "").strip(),
            "status": request.form.get("status") or "1",
            "add_shifts": request.form.get("add_shifts") or "0"
        }

        if not form_data["name"]:
            errors["name"] = "Name is required."
        if not form_data["code"]:
            errors["code"] = "Code is required."
        elif Building.query.filter_by(code=form_data["code"]).first():
            errors["code"] = "This code is already in use."

        latitude_val = None
        if form_data["latitude"]:
            try:
                latitude_val = float(form_data["latitude"])
            except ValueError:
                errors["latitude"] = "Invalid latitude."
                
        longitude_val = None
        if form_data["longitude"]:
            try:
                longitude_val = float(form_data["longitude"])
            except ValueError:
                errors["longitude"] = "Invalid longitude."

        if not errors:
            token = f"building-{uuid.uuid4().hex[:8]}"
            building = Building(
                name=form_data["name"],
                code=form_data["code"],
                address=form_data["address"],
                latitude=latitude_val,
                longitude=longitude_val,
                barcode_token=token,
                status=form_data["status"] == "1",
            )
            db.session.add(building)
            db.session.flush()

            if form_data["add_shifts"] == "1":
                from datetime import time
                morning = Shift(
                    building_id=building.id,
                    name="Morning Shift",
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    grace_minutes=10,
                    status=True,
                )
                evening = Shift(
                    building_id=building.id,
                    name="Evening Shift",
                    start_time=time(14, 0),
                    end_time=time(22, 0),
                    grace_minutes=10,
                    status=True,
                )
                db.session.add_all([morning, evening])

            db.session.commit()
            flash("Building added successfully.", "success")
            return redirect(url_for("main.building_list"))

        buildings = Building.query.order_by(Building.created_at.desc()).all()
        return render_template(
            "building/list.html",
            buildings=buildings,
            errors=errors,
            form_data=form_data,
            open_modal=True,
            page_heading="Buildings",
        )

    return render_template(
        "building/form.html",
        errors=errors,
        form_data=form_data,
        page_heading="Add Building",
    )


@main.route("/buildings/<int:building_id>/edit", methods=["POST"])
@login_required
def building_update(building_id):
    if current_user.role != "admin":
        flash("Only admin users can edit buildings.", "danger")
        return redirect(url_for("main.building_list"))

    building = Building.query.get_or_404(building_id)

    name = (request.form.get("name") or "").strip()
    code = (request.form.get("code") or "").strip()
    address = (request.form.get("address") or "").strip()
    latitude = (request.form.get("latitude") or "").strip()
    longitude = (request.form.get("longitude") or "").strip()
    status = request.form.get("status") or "1"

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("main.building_list"))

    if not code:
        flash("Code is required.", "danger")
        return redirect(url_for("main.building_list"))

    existing_code = Building.query.filter(Building.code == code, Building.id != building.id).first()
    if existing_code:
        flash("This code is already in use.", "danger")
        return redirect(url_for("main.building_list"))

    building.name = name
    building.code = code
    building.address = address
    
    if latitude:
        try:
            building.latitude = float(latitude)
        except ValueError:
            flash("Invalid latitude.", "danger")
            return redirect(url_for("main.building_list"))
    else:
        building.latitude = None
        
    if longitude:
        try:
            building.longitude = float(longitude)
        except ValueError:
            flash("Invalid longitude.", "danger")
            return redirect(url_for("main.building_list"))
    else:
        building.longitude = None

    building.status = status == "1"

    db.session.commit()
    flash("Building updated successfully.", "success")
    return redirect(url_for("main.building_list"))


@main.route("/buildings/<int:building_id>/delete", methods=["POST"])
@login_required
def building_delete(building_id):
    if current_user.role != "admin":
        flash("Only admin users can delete buildings.", "danger")
        return redirect(url_for("main.building_list"))

    building = Building.query.get_or_404(building_id)
    building.status = False
    db.session.commit()

    flash("Building deactivated successfully.", "success")
    return redirect(url_for("main.building_list"))


@main.route("/attendance")
@login_required
def attendance_list():
    if current_user.role == "admin":
        attendance_records = (
            Attendance.query.join(User, Attendance.employee_id == User.id)
            .filter(User.deleted_at.is_(None))
            .order_by(Attendance.attendance_date.desc(), Attendance.id.desc())
            .all()
        )
        page_heading = "Attendance Review"
    else:
        attendance_records = (
            Attendance.query.filter(Attendance.employee_id == current_user.id)
            .order_by(Attendance.attendance_date.desc(), Attendance.id.desc())
            .all()
        )
        page_heading = "My Attendance"

    pending_count = sum(
        1 for attendance in attendance_records if attendance.approval_status == "pending"
    )

    return render_template(
        "attendance/list.html",
        attendance_records=attendance_records,
        pending_count=pending_count,
        format_local_time=format_local_time,
        attendance_total_time=attendance_total_time,
        page_heading=page_heading,
    )


@main.route("/attendance/search", methods=["GET", "POST"])
@login_required
def attendance_search():
    attendance_records = []
    search_date = ""
    search_name = ""

    if request.method == "POST":
        search_date = request.form.get("search_date", "").strip()
        search_name = request.form.get("search_name", "").strip()

        query = Attendance.query.join(User, Attendance.employee_id == User.id).filter(User.deleted_at.is_(None))
        
        if current_user.role != "admin":
            query = query.filter(Attendance.employee_id == current_user.id)
        
        if search_date:
            try:
                date_obj = datetime.strptime(search_date, "%Y-%m-%d").date()
                query = query.filter(Attendance.attendance_date == date_obj)
            except ValueError:
                pass
                
        if search_name and current_user.role == "admin":
            query = query.filter(User.name.ilike(f"%{search_name}%"))

        attendance_records = query.order_by(Attendance.attendance_date.desc(), Attendance.id.desc()).all()

    return render_template(
        "attendance/search.html",
        attendance_records=attendance_records,
        search_date=search_date,
        search_name=search_name,
        format_local_time=format_local_time,
        attendance_total_time=attendance_total_time
    )


@main.route("/api/nearest-building", methods=["POST"])
@login_required
def nearest_building():
    payload = request.get_json(silent=True) or {}

    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required."}), 400

    buildings = (
        Building.query.filter(
            Building.status.is_(True),
            Building.latitude.isnot(None),
            Building.longitude.isnot(None),
        )
        .all()
    )

    if not buildings:
        fallback = active_employee_building(current_user)
        return jsonify({"building": building_payload(fallback) if fallback else None})

    nearest = min(
        buildings,
        key=lambda building: distance_in_meters(
            latitude,
            longitude,
            float(building.latitude),
            float(building.longitude),
        ),
    )
    distance_meters = distance_in_meters(
        latitude,
        longitude,
        float(nearest.latitude),
        float(nearest.longitude),
    )

    return jsonify({"building": building_payload(nearest, distance_meters)})


@main.route("/api/kiosk-building", methods=["POST"])
def kiosk_building():
    payload = request.get_json(silent=True) or {}

    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required."}), 400

    buildings = (
        Building.query.filter(
            Building.status.is_(True),
            Building.latitude.isnot(None),
            Building.longitude.isnot(None),
        ).all()
    )

    if not buildings:
        return jsonify({"error": "No buildings configured with coordinates."}), 404

    nearest = min(
        buildings,
        key=lambda building: distance_in_meters(
            latitude,
            longitude,
            float(building.latitude),
            float(building.longitude),
        ),
    )
    
    scan_url = url_for('main.scan_barcode', barcode_token=nearest.barcode_token, _external=True)

    return jsonify({
        "building": building_payload(nearest),
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={scan_url}"
    })


@main.route("/attendance/check-in", methods=["POST"])
@login_required
def attendance_check_in():
    if current_user.role == "admin":
        return jsonify({"error": "Admin users cannot mark personal attendance."}), 403

    payload = request.get_json(silent=True) or {}
    now_local = local_now()
    building = building_from_request(payload)

    if not building:
        return jsonify({"error": "No active building is available for attendance."}), 400

    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required to check in."}), 400

    if building.latitude is None or building.longitude is None:
        return jsonify({"error": "Building location is not configured. Cannot verify attendance distance."}), 400

    distance_meters = distance_in_meters(
        latitude,
        longitude,
        float(building.latitude),
        float(building.longitude),
    )

    if distance_meters > 100:
        return jsonify({"error": "You must be within 100 meters of the building premises to check in."}), 400

    if open_attendance_for(current_user):
        return jsonify({"error": "You are already checked in."}), 400

    if today_attendance_for(current_user):
        return jsonify({"error": "Today attendance is already recorded."}), 400

    assignment = active_shift_assignment(current_user)
    shift = assignment.shift if assignment else None
    temporary_duty = None

    if current_user.role == "temporary":
        temporary_duty = TemporaryDutyAssignment(
            temporary_user_id=current_user.id,
            building_id=building.id,
            shift_id=shift.id if shift else None,
            duty_date=now_local.date(),
            status="pending",
            notes="Created from temporary user check-in.",
        )
        db.session.add(temporary_duty)
        db.session.flush()

    approval_status = "pending" if current_user.role == "temporary" or not shift else "approved"

    source = "manual"
    scanned_building_id = session.get("scanned_building_id")
    if scanned_building_id and building and building.id == scanned_building_id:
        source = "barcode"
        session.pop("scanned_building_id", None)
        session.pop("scanned_building_name", None)

    attendance = Attendance(
        employee_id=current_user.id,
        temporary_duty_id=temporary_duty.id if temporary_duty else None,
        building_id=building.id,
        shift_id=shift.id if shift else None,
        attendance_date=now_local.date(),
        check_in_at=utc_now_naive(),
        timezone_name="Asia/Karachi",
        timezone_offset_minutes=300,
        check_in_status=check_in_status_for(shift, now_local),
        source=source,
        approval_status=approval_status,
        notes="Temporary attendance pending admin approval." if current_user.role == "temporary" else None,
    )

    db.session.add(attendance)
    db.session.commit()

    return jsonify({"attendance": attendance_payload(attendance)})


@main.route("/attendance/check-out", methods=["POST"])
@login_required
def attendance_check_out():
    if current_user.role == "admin":
        return jsonify({"error": "Admin users cannot mark personal attendance."}), 403

    attendance = open_attendance_for(current_user)
    if not attendance:
        return jsonify({"error": "No open attendance found for checkout."}), 400

    payload = request.get_json(silent=True) or {}
    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required to check out."}), 400

    building = attendance.building
    if building.latitude is None or building.longitude is None:
        return jsonify({"error": "Building location is not configured. Cannot verify attendance distance."}), 400

    distance_meters = distance_in_meters(
        latitude,
        longitude,
        float(building.latitude),
        float(building.longitude),
    )

    if distance_meters > 100:
        return jsonify({"error": "You must be within 100 meters of the building premises to check out."}), 400

    now_local = local_now()
    attendance.check_out_at = utc_now_naive()
    attendance.check_out_status = check_out_status_for(attendance.shift, now_local)

    if current_user.role == "temporary":
        attendance.approval_status = "pending"
        if attendance.temporary_duty:
            attendance.temporary_duty.status = "completed"

    db.session.commit()

    return jsonify({"attendance": attendance_payload(attendance)})


@main.route("/attendance/<int:attendance_id>/approve", methods=["POST"])
@login_required
def approve_attendance(attendance_id):
    wants_json = request.is_json or request.accept_mimetypes.best == "application/json"

    if current_user.role != "admin":
        if wants_json:
            return jsonify({"error": "Only admin users can approve attendance."}), 403

        flash("Only admin users can approve attendance.", "danger")
        return redirect(url_for("main.attendance_list"))

    attendance = Attendance.query.get_or_404(attendance_id)

    if attendance.employee.role == "temporary" and not attendance.employee.status:
        message = "First update the temporary user's status, then approve their attendance."
        if wants_json:
            return jsonify({"error": message}), 400

        flash(message, "warning")
        return redirect(url_for("main.attendance_list"))

    if not attendance.check_in_at or not attendance.check_out_at:
        message = "Attendance can be approved after both check in and check out are recorded."
        if wants_json:
            return jsonify({"error": message}), 400

        flash(message, "warning")
        return redirect(url_for("main.attendance_list"))

    attendance.approval_status = "approved"
    attendance.approved_by_user_id = current_user.id
    attendance.approved_at = utc_now_naive()

    if attendance.temporary_duty:
        attendance.temporary_duty.status = "approved"
        attendance.temporary_duty.approved_by_user_id = current_user.id
        attendance.temporary_duty.approved_at = attendance.approved_at

    db.session.commit()

    if wants_json:
        return jsonify({"attendance": attendance_payload(attendance)})

    flash("Attendance approved successfully.", "success")
    return redirect(url_for("main.attendance_list"))


@main.route("/attendance/<int:attendance_id>/reject", methods=["POST"])
@login_required
def reject_attendance(attendance_id):
    wants_json = request.is_json or request.accept_mimetypes.best == "application/json"

    if current_user.role != "admin":
        if wants_json:
            return jsonify({"error": "Only admin users can reject attendance."}), 403

        flash("Only admin users can reject attendance.", "danger")
        return redirect(url_for("main.attendance_list"))

    attendance = Attendance.query.get_or_404(attendance_id)
    attendance.approval_status = "rejected"
    attendance.approved_by_user_id = current_user.id
    attendance.approved_at = utc_now_naive()

    if attendance.temporary_duty:
        attendance.temporary_duty.status = "rejected"
        attendance.temporary_duty.approved_by_user_id = current_user.id
        attendance.temporary_duty.approved_at = attendance.approved_at

    db.session.commit()

    if wants_json:
        return jsonify({"attendance": attendance_payload(attendance)})

    flash("Attendance rejected.", "success")
    return redirect(url_for("main.attendance_list"))
