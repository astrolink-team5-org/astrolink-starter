from flask import Blueprint, abort, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app.models import (
    AuditEvent, User, Satellite, GroundStation, TelemetryReading,
    CommandLog, Subscriber, LegacyAccessLog, db
)

from app.simulator import COMMANDS, execute_command

from app.auth import getAuthorizedRoute, record_audit_event

from show_data import fmt

commands_bp = Blueprint("commands", __name__)


@commands_bp.route("/display_satellites_command", methods=["GET"])
def display_satellites_command():
    sats = []
    for s in Satellite.query.order_by(Satellite.name):
        sats.append(f"  {s.name}  {s.status:<11} {s.orbit_altitude_km:>6} km  fuel {s.fuel_remaining_pct:>5}%  "
                f"fw {s.firmware_version:<10} antenna {s.antenna_bearing_deg:>5}  {s.power_mode:<9} "
                f"{s.subscribers_served:>5} customers  {s.coverage_region}")
    return sats
        
@commands_bp.route("/display_ground_stations_command", methods=["GET"])
def display_ground_stations_command():
    stats = []
    for g in GroundStation.query.order_by(GroundStation.name):
        stats.append(f"  {g.name}  {g.status:<9} {g.ip_address:<12} {g.location}")
    return stats

@commands_bp.route("/display_telemetry_command", methods=["GET"])
def display_telemetry_command():
    tels = []
    for t in TelemetryReading.query.order_by(TelemetryReading.timestamp.desc()).limit(20):
        gs = t.ground_station.name if t.ground_station else "NONE"
        tels.append(f"  {fmt(t.timestamp)}  {t.satellite.name}  via {gs:<6} battery {t.battery_pct:>5}%  "
                f"temp {t.temperature_c:>6} C  signal {t.signal_dbm} dBm  alt {t.altitude_km} km")

    return tels


@commands_bp.route("/ping_command", methods=["POST"])
@login_required
def ping_command():
    allowed_roles = {"junior", "midlevel", "senior", "admin"}
    if current_user.permissions not in allowed_roles:
        abort(403)

    sat_name = request.form.get("satellite", "").strip()
    satellite = Satellite.query.filter_by(name=sat_name).first()
    if satellite is None:
        abort(404)

    execute_command(satellite, "ping", user_id=current_user.id)
    return getAuthorizedRoute()

@commands_bp.route("/power_mode_command", methods=["POST"])
@login_required
def power_mode_command():
    allowed_roles = {"junior", "midlevel", "senior", "admin"}
    if current_user.permissions not in allowed_roles:
        abort(403)

    sat_name = request.form.get("satellite", "").strip()
    satellite = Satellite.query.filter_by(name=sat_name).first()
    if satellite is None:
        abort(404)

    mode = request.form.get("mode", "").strip()
    power_modes = {"0": "low_power", "1": "normal"}
    if mode not in power_modes:
        abort(400)

    execute_command(satellite, "power_mode", power_modes[mode], user_id=current_user.id)

    return getAuthorizedRoute()

@commands_bp.route("/resume_normal_command", methods=["POST"])
@login_required
def resume_normal_command():
    allowed_roles = {"junior", "midlevel", "senior", "admin"}
    if current_user.permissions not in allowed_roles:
        abort(403)

    sat_name = request.form.get("satellite", "").strip()
    satellite = Satellite.query.filter_by(name=sat_name).first()
    if satellite is None:
        abort(404)

    execute_command(satellite, "resume", user_id=current_user.id)
    return getAuthorizedRoute()

@commands_bp.route("/safe_mode_command", methods=["POST"])
@login_required
def safe_mode_command():
    allowed_roles = {"junior", "midlevel", "senior", "admin"}
    if current_user.permissions not in allowed_roles:
        abort(403)

    sat_name = request.form.get("satellite", "").strip()
    satellite = Satellite.query.filter_by(name=sat_name).first()
    if satellite is None:
        abort(404)

    execute_command(satellite, "safe_mode", user_id=current_user.id)
    return getAuthorizedRoute()

@commands_bp.route("/aim_satellite_command", methods=["POST"])
@login_required
def aim_satellite_command():
    allowed_roles = {"junior", "midlevel", "senior", "admin"}
    if current_user.permissions not in allowed_roles:
        record_audit_event(
            event_type="command_antenna_point",
            outcome="denied",
            actor_user_id=current_user.id,
            reason_code="insufficient_permissions",
        )
        abort(403)

    sat_name = request.form.get("satellite", "").strip()
    satellite = Satellite.query.filter_by(name=sat_name).first()
    if satellite is None:
        abort(404)

    angle = request.form.get("aim_angle", "").strip()
    try:
        execute_command(satellite, "antenna_point", angle, user_id=current_user.id)
    except ValueError as e:
        db.session.rollback()
        db.session.add(CommandLog(
            satellite_id=satellite.id,
            user_id=current_user.id,
            command_type="antenna_point",
            parameter=angle[:100],
            status="failed",
            description=str(e),
        ))
        db.session.commit()
        abort(400, description=str(e))
    return getAuthorizedRoute()
    

@commands_bp.route("/adjust_orbit_command", methods=["GET", "POST"])
def adjust_orbit_command():
    if request.method == "POST":
        sat_name = request.form.get("satellite", "").strip()
        satellite = Satellite.query.filter_by(name=sat_name).first()
        km = request.form.get("km_change", "").strip()
    execute_command(satellite, "orbit_adjust", km)
    return getAuthorizedRoute()

@commands_bp.route("/firmware_update_command", methods=["GET", "POST"])
def firmware_update_command():
    if request.method == "POST":
        sat_name = request.form.get("satellite", "").strip()
        satellite = Satellite.query.filter_by(name=sat_name).first()
        version = request.form.get("version", "").strip()
    execute_command(satellite, "firmware_update", version)
    return getAuthorizedRoute()

@commands_bp.route("/deorbit_satellite_command", methods=["GET", "POST"])
def deorbit_satellite_command():
    if request.method == "POST":
        sat_name = request.form.get("satellite", "").strip()
        satellite = Satellite.query.filter_by(name=sat_name).first()
    execute_command(satellite, "deorbit")
    return getAuthorizedRoute()

@commands_bp.route("/display_subscribers_command", methods=["GET"])
def display_subscribers_command():
    subscribers = []
    for s in Subscriber.query.order_by(Subscriber.id):
        subscribers.append(f"  {s.full_name:<16} {s.email:<30} {s.phone}  {s.home_address}")
    return subscribers

@commands_bp.route("/display_users_command", methods=["GET"])
def display_users_command():
    users = []
    for u in User.query.order_by(User.id):
        users.append(f"  {u.username:<10} {u.display_name:<17} {u.job_title:<20} {u.permissions:<20} {u.employment_status}")
    return users

@commands_bp.route("/display_LegacyAccessLog_command", methods=["GET"])
def display_LegacyAccessLog_command():
    access_log = []
    for a in LegacyAccessLog.query.order_by(LegacyAccessLog.timestamp.desc()).limit(40):
        access_log.append(f"  {fmt(a.timestamp)}  {a.username:<10} {a.ip_address:<14} {'ok' if a.success else 'FAILED'}")    
    return access_log

@commands_bp.route("/display_AuditEvents_command", methods=["GET"])
def display_AuditEvents_command():
    events = []
    for a in AuditEvent.query.order_by(AuditEvent.timestamp.desc()):
        events.append(f"  {fmt(a.timestamp)}  {a.event_type:<14} {a.outcome:<14}")
    return events

@commands_bp.route("/add_user_command", methods=["GET", "POST"])
def add_user_command():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        display_name = request.form.get("display_name", "").strip()
        job_title = request.form.get("job_title", "").strip()
        permissions = request.form.get("permissions", "").strip()

        user = User(username=username, 
                    display_name=display_name, 
                    job_title=job_title,
                    permissions=permissions)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

    return getAuthorizedRoute()

@commands_bp.route("/remove_user_command", methods=["GET", "POST"])
def remove_user_command():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = User.query.filter_by(username=username).first()

        user.employment_status = "left"
        db.session.commit()
        
    return getAuthorizedRoute()

@commands_bp.route("/assign_user_permissions_command", methods=["GET", "POST"])
def assign_user_permissions_command():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        permissions = request.form.get("permissions", "").strip()

        user = User.query.filter_by(username=username).first()
        user.permissions = permissions
        db.session.commit()

    return getAuthorizedRoute()

