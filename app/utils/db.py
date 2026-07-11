"""
WeatherWise — Database Utilities
---------------------------------
Provides helpers to query and update the SQLite database.
Initialises tables on startup if they do not exist.
"""

import os
import sqlite3

from flask import current_app, g

DB_FILE = "weatherwise.db"


def get_db():
    """
    Establish a connection to SQLite database.
    Reuses connection if already open in current request context (Flask g).
    """
    if "db" not in g:
        db_path = os.path.join(current_app.root_path, "..", DB_FILE)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    """Close connection at the end of a request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """
    Register teardown function and create tables.
    Called once during application factory setup.
    """
    app.teardown_appcontext(close_db)

    db_path = os.path.join(app.root_path, "..", DB_FILE)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Create users table
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
        # Upgrade databases created before password recovery was introduced.
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(users)")}
        if "recovery_code_hash" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN recovery_code_hash TEXT")
        conn.commit()
    finally:
        conn.close()
