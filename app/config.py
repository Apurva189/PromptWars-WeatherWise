"""
WeatherWise — Flask Configuration
------------------------------------
Three config classes for different environments:
  - DevelopmentConfig : local dev, debug on
  - ProductionConfig  : deployed app, debug off, secure cookies
  - TestingConfig     : pytest, AI calls mocked

Usage in app factory:
    app.config.from_object(config['development'])
"""

import os
import secrets
from dotenv import load_dotenv

# Load .env file if present (local dev only; Render/Railway inject env vars directly)
load_dotenv()


class _BaseConfig:
    """Shared settings across all environments."""

    # ── Flask Core ────────────────────────────────────────────
    # Require SECRET_KEY from env; fall back to random key for dev convenience
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # ── Gemini AI ─────────────────────────────────────────────
    GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

    # ── Rate Limiting ─────────────────────────────────────────
    RATELIMIT_DEFAULT: str = "100 per minute"
    RATELIMIT_STORAGE_URL: str = "memory://"  # swap to Redis URL in prod if needed
    RATELIMIT_HEADERS_ENABLED: bool = True

    # ── Session Security ──────────────────────────────────────
    SESSION_COOKIE_HTTPONLY: bool = True   # JS cannot access session cookie
    SESSION_COOKIE_SAMESITE: str = "Lax"  # CSRF mitigation

    # ── Request Limits ────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 1 * 1024 * 1024  # 1 MB max request body


class DevelopmentConfig(_BaseConfig):
    """Local development — debug enabled, relaxed security."""
    DEBUG: bool = True
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = False  # HTTP is fine locally


class ProductionConfig(_BaseConfig):
    """Deployed app — strict security, no debug output."""
    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = True  # HTTPS only in production


class TestingConfig(_BaseConfig):
    """Pytest environment — AI calls will be mocked."""
    DEBUG: bool = True
    TESTING: bool = True
    # Use a fixed key so session data is consistent between requests in tests
    SECRET_KEY: str = "test-secret-key-do-not-use-in-prod"
    GEMINI_API_KEY: str = "test-api-key"
    SESSION_COOKIE_SECURE: bool = False
    # Disable rate limiting during tests for clean assertions
    RATELIMIT_ENABLED: bool = False


# ── Config registry ───────────────────────────────────────────
# Import this dict in the app factory to select the right config by name
config: dict = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
