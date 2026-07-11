"""
WeatherWise — Authentication Route Tests
------------------------------------------
Tests registration, login, logout, and protected routes using SQLite.

Run with:  pytest tests/test_auth.py -v
"""

import os
import sqlite3
import pytest
from flask import session

from app import create_app
from app.utils.db import get_db, DB_FILE


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
                password_hash TEXT NOT NULL
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
    import app.utils.db
    original_get_db = app.utils.db.get_db
    app.utils.db.get_db = test_get_db

    yield application

    # Tear down patches and delete temp db file
    app.utils.db.get_db = original_get_db
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
            data={"username": "newUser1", "password": "password123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Registration successful" in resp.data
        assert b"Welcome Back" in resp.data  # Redirects to login page

    def test_register_duplicate_username_fails(self, client):
        # Register once
        client.post(
            "/register",
            data={"username": "duplicateUser", "password": "password123"},
        )
        # Register duplicate username
        resp = client.post(
            "/register",
            data={"username": "duplicateUser", "password": "differentPassword"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Username already exists" in resp.data

    def test_register_short_password_fails(self, client):
        resp = client.post(
            "/register",
            data={"username": "user1", "password": "123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Password must be at least 6 characters" in resp.data

    def test_register_invalid_username_fails(self, client):
        resp = client.post(
            "/register",
            data={"username": "", "password": "password123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"cannot be empty" in resp.data or b"Invalid username" in resp.data


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
            data={"username": "authuser", "password": "password123"},
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
            data={"username": "wrongpassuser", "password": "password123"},
        )
        resp = client.post(
            "/login",
            data={"username": "wrongpassuser", "password": "wrongpassword"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Incorrect username or password" in resp.data

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
            data={"username": "dashboarduser", "password": "password123"},
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
            data={"username": "logoutuser", "password": "password123"},
        )
        client.post(
            "/login",
            data={"username": "logoutuser", "password": "password123"},
        )
        # Verify user is logged in
        resp = client.get("/dashboard")
        assert resp.status_code == 200

        # Logout
        resp = client.get("/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Welcome Back" in resp.data

        # Verify page is no longer accessible
        resp_after = client.get("/dashboard")
        assert resp_after.status_code == 302
