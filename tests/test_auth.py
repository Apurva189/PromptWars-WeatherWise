"""
WeatherWise — Authentication Route Tests
------------------------------------------
Tests registration, login, logout, and protected routes using SQLite.

Run with:  pytest tests/test_auth.py -v
"""

import os
import re
import sqlite3

import pytest

from app import create_app


@pytest.fixture(scope="function")
def app():
    """Create a temporary database and Flask application for testing."""
    # Configure testing app
    application = create_app("testing")
    application.config["WTF_CSRF_ENABLED"] = False

    # Force a unique test database file for safety and isolation
    test_db = "test_weatherwise.db"
    application.root_path_parent = os.path.dirname(application.root_path)
    test_db_path = os.path.join(application.root_path_parent, test_db)

    # Clean up test database if it exists from a crashed previous run
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # Initialize tables on test db
    conn = sqlite3.connect(test_db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                recovery_code_hash TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    # Override the DB retrieval during app context lifetime
    def test_get_db():
        from flask import g

        if "db" not in g:
            g.db = sqlite3.connect(test_db_path)
            g.db.row_factory = sqlite3.Row
        return g.db

    # Patch the get_db import inside app context
    import app.routes.main
    import app.utils.db

    original_get_db = app.utils.db.get_db
    original_main_get_db = app.routes.main.get_db
    app.utils.db.get_db = test_get_db
    app.routes.main.get_db = test_get_db

    yield application

    # Tear down patches and delete temp db file
    app.utils.db.get_db = original_get_db
    app.routes.main.get_db = original_main_get_db
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


# ════════════════════════════════════════════════════════════
# REGISTER TESTS
# ════════════════════════════════════════════════════════════


class TestRegister:
    def test_register_page_loads(self, client):
        resp = client.get("/register")
        assert resp.status_code == 200
        assert b"Create Account" in resp.data

    def test_register_success(self, client):
        resp = client.post(
            "/register",
            data={
                "username": "newUser1",
                "password": "password123",
                "confirm_password": "password123",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Registration successful" in resp.data
        assert b"Welcome Back" in resp.data  # Redirects to login page

    def test_register_duplicate_username_fails(self, client):
        # Register once
        client.post(
            "/register",
            data={
                "username": "duplicateUser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        # Register duplicate username
        resp = client.post(
            "/register",
            data={
                "username": "duplicateUser",
                "password": "differentPassword",
                "confirm_password": "differentPassword",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Username already exists" in resp.data

    def test_register_short_password_fails(self, client):
        resp = client.post(
            "/register",
            data={"username": "user1", "password": "123", "confirm_password": "123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Password must be at least 6 characters" in resp.data

    def test_register_invalid_username_fails(self, client):
        resp = client.post(
            "/register",
            data={"username": "", "password": "password123", "confirm_password": "password123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"cannot be empty" in resp.data or b"Invalid username" in resp.data

    def test_register_password_confirmation_must_match(self, client):
        resp = client.post(
            "/register",
            data={
                "username": "user2",
                "password": "password123",
                "confirm_password": "different123",
            },
            follow_redirects=True,
        )
        assert b"Passwords do not match" in resp.data


# ════════════════════════════════════════════════════════════
# LOGIN TESTS
# ════════════════════════════════════════════════════════════


class TestLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Welcome Back" in resp.data

    def test_login_success(self, client):
        # First register
        client.post(
            "/register",
            data={
                "username": "authuser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        # Now login
        resp = client.post(
            "/login",
            data={"username": "authuser", "password": "password123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data
        assert b"Logout" in resp.data

    def test_login_incorrect_password_fails(self, client):
        client.post(
            "/register",
            data={
                "username": "wrongpassuser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        resp = client.post(
            "/login",
            data={"username": "wrongpassuser", "password": "wrongpassword"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Incorrect username or password" in resp.data


class TestForgotPassword:
    def test_forgot_password_page_loads(self, client):
        resp = client.get("/forgot-password")
        assert resp.status_code == 200
        assert b"Reset Password" in resp.data

    def test_password_can_be_reset_with_recovery_code(self, client):
        registration = client.post(
            "/register",
            data={
                "username": "resetuser",
                "password": "oldpassword",
                "confirm_password": "oldpassword",
            },
            follow_redirects=True,
        )
        match = re.search(rb"recovery code now: ([A-F0-9]{12})", registration.data)
        assert match is not None

        reset = client.post(
            "/forgot-password",
            data={
                "username": "resetuser",
                "recovery_code": match.group(1).decode(),
                "password": "newpassword",
                "confirm_password": "newpassword",
            },
            follow_redirects=True,
        )
        assert b"Password reset successful" in reset.data

        old_login = client.post(
            "/login",
            data={"username": "resetuser", "password": "oldpassword"},
            follow_redirects=True,
        )
        assert b"Incorrect username or password" in old_login.data

        new_login = client.post(
            "/login",
            data={"username": "resetuser", "password": "newpassword"},
            follow_redirects=True,
        )
        assert b"Dashboard" in new_login.data

    def test_reset_rejects_mismatched_passwords(self, client):
        resp = client.post(
            "/forgot-password",
            data={
                "username": "someuser",
                "recovery_code": "ABCDEF123456",
                "password": "newpassword",
                "confirm_password": "differentpassword",
            },
            follow_redirects=True,
        )
        assert b"Passwords do not match" in resp.data


class TestCsrfProtection:
    def test_form_post_without_token_is_rejected(self, app, client):
        app.config["CSRF_ENABLED"] = True
        try:
            client.get("/login")
            response = client.post("/login", data={"username": "user", "password": "password"})
            assert response.status_code == 400
            assert b"CSRF" in response.data
        finally:
            app.config["CSRF_ENABLED"] = False

    def test_form_post_with_token_passes_csrf_check(self, app, client):
        app.config["CSRF_ENABLED"] = True
        try:
            client.get("/login")
            with client.session_transaction() as session:
                token = session["csrf_token"]
            response = client.post(
                "/login",
                data={
                    "username": "unknown-user",
                    "password": "password",
                    "csrf_token": token,
                },
            )
            assert response.status_code == 200
            assert b"Incorrect username or password" in response.data
        finally:
            app.config["CSRF_ENABLED"] = False

    def test_login_nonexistent_user_fails(self, client):
        resp = client.post(
            "/login",
            data={"username": "nonexistent", "password": "password123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Incorrect username or password" in resp.data


# ════════════════════════════════════════════════════════════
# PROTECTED ROUTES TESTS
# ════════════════════════════════════════════════════════════


class TestProtectedRoutes:
    def test_dashboard_redirects_if_not_logged_in(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 302
        assert "/login" in resp.location

    def test_api_returns_401_if_not_logged_in(self, client):
        resp = client.get("/api/weather?city=Mumbai")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data
        assert "Authentication required" in data["error"]

    def test_dashboard_accessible_if_logged_in(self, client):
        # Register & Login
        client.post(
            "/register",
            data={
                "username": "dashboarduser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        client.post(
            "/login",
            data={"username": "dashboarduser", "password": "password123"},
        )
        # Verify access
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data

    def test_logout_clears_session(self, client):
        # Register & Login
        client.post(
            "/register",
            data={
                "username": "logoutuser",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        client.post(
            "/login",
            data={"username": "logoutuser", "password": "password123"},
        )
        # Verify user is logged in
        resp = client.get("/dashboard")
        assert resp.status_code == 200

        # Logout
        resp = client.post("/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Welcome Back" in resp.data

        # Verify page is no longer accessible
        resp_after = client.get("/dashboard")
        assert resp_after.status_code == 302
