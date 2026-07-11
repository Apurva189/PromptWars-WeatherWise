"""
WeatherWise — Application Factory
------------------------------------
Uses the Flask application-factory pattern so the app object is created
on demand (important for testing and multi-worker deployments).

Call create_app() with an environment name to get a fully configured app.
"""

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import config

# ── Shared extension instances ─────────────────────────────────
# Created here (not bound to an app yet) so blueprints can import them.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)


def create_app(env_name: str = "default") -> Flask:
    """
    Factory function — builds and returns a configured Flask application.

    Args:
        env_name: One of 'development', 'production', 'testing', 'default'.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Load config ───────────────────────────────────────────
    app.config.from_object(config[env_name])

    # ── Initialize extensions & database ──────────────────────
    limiter.init_app(app)
    _configure_security_headers(app)

    from app.utils.db import init_db
    init_db(app)

    # ── Register blueprints ───────────────────────────────────
    from app.routes.main import main_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Register error handlers ───────────────────────────────
    _register_error_handlers(app)

    return app


def _configure_security_headers(app: Flask) -> None:
    """
    Attach an after-request hook that injects standard security headers.

    We avoid flask-talisman in dev to prevent HTTPS redirect loops, but
    still set headers so tests reflect production behaviour.
    """

    @app.after_request
    def set_security_headers(response):
        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Block clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Basic XSS protection for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Tell browsers to only send the referrer to same-origin pages
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy — allow fonts & scripts from CDNs used in templates
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.open-meteo.com https://geocoding-api.open-meteo.com;"
        )
        return response


def _register_error_handlers(app: Flask) -> None:
    """Return JSON error responses for common HTTP errors."""

    from flask import jsonify

    @app.errorhandler(404)
    def not_found(_err):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_err):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(err):
        return jsonify({"error": f"Rate limit exceeded: {err.description}"}), 429

    @app.errorhandler(500)
    def internal_error(_err):
        return jsonify({"error": "Internal server error"}), 500
