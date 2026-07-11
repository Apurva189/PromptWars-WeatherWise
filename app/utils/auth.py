"""
WeatherWise — Authentication Decorator
----------------------------------------
Protects dashboard and API routes by verifying the user is logged in.
"""

from functools import wraps
from flask import session, redirect, url_for, request, jsonify


def login_required(f):
    """
    Decorator to ensure user is authenticated.
    Redirects HTML requests to /login, returns 401 JSON for API requests.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            # If requesting an API endpoint, return JSON error
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required. Please log in."}), 401

            # Otherwise, redirect to login page
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return decorated_function
