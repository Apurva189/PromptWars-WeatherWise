"""Small, dependency-free CSRF protection for forms and JSON API requests."""

import secrets
from hmac import compare_digest

from flask import abort, request, session


def init_csrf(app) -> None:
    """Register token creation, template access, and unsafe-request validation."""

    def csrf_token() -> str:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def protect_unsafe_requests():
        if app.config.get("CSRF_ENABLED", True) is False:
            return None
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None

        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        if not expected or not supplied or not compare_digest(expected, supplied):
            abort(400, description="Invalid or missing CSRF token.")
        return None
