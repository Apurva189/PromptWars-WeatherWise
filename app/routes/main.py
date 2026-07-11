"""
WeatherWise — Main Page & Authentication Routes
------------------------------------------------
Serves main pages (landing, dashboard) and manages user login/registration/logout.
"""

import sqlite3
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from app.utils.db import get_db
from app.utils.auth import login_required
from app.utils.validators import sanitise_text

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    """Landing page — overview and call-to-action."""
    return render_template("index.html")


@main_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """Main application dashboard (requires authentication)."""
    return render_template("dashboard.html", username=session.get("username"))


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user account."""
    # If already logged in, skip register
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username_raw = request.form.get("username", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Clean/sanitize username using validator rules
        username, err = sanitise_text(username_raw)
        if err or not username:
            flash(err or "Invalid username.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        db = get_db()
        recovery_code = secrets.token_hex(6).upper()
        try:
            db.execute(
                "INSERT INTO users (username, password_hash, recovery_code_hash) VALUES (?, ?, ?)",
                (
                    username,
                    generate_password_hash(password),
                    generate_password_hash(recovery_code),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Username already exists. Please choose a different one.", "error")
            return render_template("register.html")

        flash(
            f"Registration successful! Save this recovery code now: {recovery_code}",
            "success",
        )
        return redirect(url_for("main.login"))

    return render_template("register.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log in an existing user."""
    # If already logged in, redirect to dashboard
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username_raw = request.form.get("username", "")
        password = request.form.get("password", "")

        username, err = sanitise_text(username_raw)
        if err or not username:
            flash(err or "Invalid username.", "error")
            return render_template("login.html")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "error")
            return render_template("login.html")

        # Clear session and store user info
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Reset a password using the recovery code issued at registration."""
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username_raw = request.form.get("username", "")
        recovery_code = request.form.get("recovery_code", "").strip().upper()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        username, err = sanitise_text(username_raw)
        if err or not username:
            flash(err or "Invalid username.", "error")
            return render_template("forgot_password.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("forgot_password.html")
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("forgot_password.html")

        db = get_db()
        user = db.execute(
            "SELECT id, recovery_code_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        valid_code = (
            user is not None
            and user["recovery_code_hash"]
            and check_password_hash(user["recovery_code_hash"], recovery_code)
        )
        if not valid_code:
            flash("Invalid username or recovery code.", "error")
            return render_template("forgot_password.html")

        # Rotate the recovery code after use so it cannot reset the account twice.
        new_recovery_code = secrets.token_hex(6).upper()
        db.execute(
            "UPDATE users SET password_hash = ?, recovery_code_hash = ? WHERE id = ?",
            (
                generate_password_hash(password),
                generate_password_hash(new_recovery_code),
                user["id"],
            ),
        )
        db.commit()
        flash(
            f"Password reset successful. Save your new recovery code: {new_recovery_code}",
            "success",
        )
        return redirect(url_for("main.login"))

    return render_template("forgot_password.html")


@main_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear session data and redirect to landing page."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))


@main_bp.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint used by deployment platforms to verify the app is running.
    Returns a simple JSON OK.
    """
    return jsonify({"status": "ok", "service": "WeatherWise"}), 200
