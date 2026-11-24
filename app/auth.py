"""
Authentication routes — login, register, logout.
This is provided for you. You can modify it if needed.

Notice what this does NOT do (these are things teams build):
  - check whether the user still works here (employment_status)
  - limit failed login attempts
  - record logins anywhere
  - expire sessions
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_user, logout_user, login_required, current_user
from app.models import AuditEvent, User, db, Satellite

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return getAuthorizedRoute()
    return redirect(url_for("auth.login"))

# home routes

@auth_bp.route("/home")
@login_required
def home():
    """Placeholder page after login. Point this at your own tool's main page."""
    return render_template("home.html")


@auth_bp.route("/visitor")
@login_required
def visitor():
    """Visitor Home"""
    return render_template("visitor.html")

@auth_bp.route("/junior")
@login_required
def junior():
    """Junior Home"""
    return render_template("junior.html")

@auth_bp.route("/midlevel")
@login_required
def midlevel():
    """Mid Home"""
    return render_template("midlevel.html")

@auth_bp.route("/senior")
@login_required
def senior():
    """Senior Home"""
    return render_template("senior.html")


@auth_bp.route("/admin")
@login_required
def admin():
    if current_user.permissions != "admin":
        abort(403)

    satellites = Satellite.query.all()
    
    
    return render_template("admin.html")


# commands

def getAuthorizedRoute():

    if current_user.permissions == "visitor":
        return redirect(url_for("auth.visitor"))
    
    elif current_user.permissions == "junior":
        return redirect(url_for("auth.junior"))
    
    elif current_user.permissions == "midlevel":
        return redirect(url_for("auth.midlevel"))
    
    elif current_user.permissions == "senior":
            return redirect(url_for("auth.senior"))
    
    elif current_user.permissions == "admin":
            return redirect(url_for("auth.admin"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return getAuthorizedRoute()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        # add login event to audit log
        if user is None:
            reason_code = "unknown_username"
        elif not user.check_password(password):
            reason_code = "invalid_password"
        elif user.employment_status == "left":
            reason_code = "account_inactive"
        elif not login_user(user):
            reason_code = "account_inactive"
        else: # successful login
            session["session_version"] = user.session_version
            record_audit_event(
                event_type="login",
                outcome="success",
                actor_user_id=user.id
            )
            flash(f"Logged in as {user.display_name or user.username}.", "success")
            return getAuthorizedRoute()


        record_audit_event(
            event_type = "login",
            outcome = "denied",
            target_user_id=user.id if user is not None else None,
            reason_code=reason_code,
        )
        if reason_code == "account_inactive":
            flash(
                "Your account is inactive. Please contact an administrator to reactivate it.",
                "danger",
            )
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
            return redirect(url_for("auth.register"))

        user = User(username=username, display_name=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    record_audit_event(event_type="logout", outcome="success", actor_user_id=user_id)
    return redirect(url_for("auth.login"))


def record_audit_event(event_type, outcome, *, actor_user_id=None, target_user_id=None, reason_code=None):
    """Record an audit event in the database."""
    event = AuditEvent(
        event_type=event_type,
        outcome=outcome,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        reason_code=reason_code,
        ip_address=request.remote_addr,
    )
    db.session.add(event)
    db.session.commit()
