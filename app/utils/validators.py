"""
WeatherWise — Input Validators & Sanitizers
---------------------------------------------
All user-supplied data is validated and sanitised here before it reaches
the AI service layer.  This is the first line of defence against:
  - XSS (cross-site scripting) via injected HTML/JS
  - Prompt injection via malicious AI instructions in user input
  - Oversized payloads that could bloat AI context windows

Public functions return (cleaned_value, error_message | None).
A non-None error message means validation failed.
"""

import re
import html
from datetime import datetime, date


# ── Constants ─────────────────────────────────────────────────
MAX_TEXT_LENGTH = 500          # Max chars for free-text fields
MAX_CITY_LENGTH = 100          # Max chars for city/location fields
MAX_FAMILY_SIZE = 50           # Reasonable upper bound
MIN_FAMILY_SIZE = 1

# Allowed language names
SUPPORTED_LANGUAGES = {
    "English", "Hindi", "Bengali", "Tamil", "Telugu", "Marathi",
    "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia", "Urdu",
}

# Allowed enum values for various fields
ALLOWED_PHASES = {"pre-monsoon", "active-monsoon", "post-monsoon", "before", "during", "after"}
ALLOWED_HOUSING_TYPES = {"apartment", "independent-house", "rural-home"}
ALLOWED_TRANSPORT_MODES = {"car", "bike", "bus", "train", "flight", "walk"}
ALLOWED_VULNERABILITIES = {
    "elderly", "infant", "toddler", "disability", "medical-equipment",
    "pregnant", "chronic-illness", "pets",
}

# Regex: city names may contain letters, spaces, hyphens, dots, and apostrophes
_CITY_NAME_RE = re.compile(r"^[\w\s\-\.\']+$", re.UNICODE)


def sanitise_text(text: str) -> tuple[str, str | None]:
    """
    Sanitise a free-text field (chat messages, custom inputs).

    - Strips leading/trailing whitespace
    - HTML-escapes special characters to prevent XSS
    - Removes null bytes
    - Enforces maximum length

    Returns:
        (sanitised_text, None) on success
        ("", error_message) on failure
    """
    if not isinstance(text, str):
        return "", "Input must be a string."

    # Strip and remove null bytes
    cleaned = text.strip().replace("\x00", "")

    if not cleaned:
        return "", "Input cannot be empty."

    if len(cleaned) > MAX_TEXT_LENGTH:
        return "", f"Input too long. Maximum {MAX_TEXT_LENGTH} characters allowed."

    # HTML-escape to neutralise any injected markup
    sanitised = html.escape(cleaned, quote=True)

    return sanitised, None


def sanitise_city(city: str) -> tuple[str, str | None]:
    """
    Validate and sanitise a city/location name.

    Returns:
        (city_name, None) on success or ("", error_message) on failure.
    """
    if not isinstance(city, str):
        return "", "City name must be a string."

    cleaned = city.strip()

    if not cleaned:
        return "", "City name cannot be empty."

    if len(cleaned) > MAX_CITY_LENGTH:
        return "", f"City name too long. Maximum {MAX_CITY_LENGTH} characters."

    if not _CITY_NAME_RE.match(cleaned):
        return "", "City name contains invalid characters."

    return cleaned, None


def validate_family_size(value) -> tuple[int, str | None]:
    """
    Validate family size is an integer in the expected range.

    Returns:
        (family_size_int, None) on success or (0, error_message) on failure.
    """
    try:
        size = int(value)
    except (TypeError, ValueError):
        return 0, "Family size must be a whole number."

    if size < MIN_FAMILY_SIZE:
        return 0, f"Family size must be at least {MIN_FAMILY_SIZE}."

    if size > MAX_FAMILY_SIZE:
        return 0, f"Family size cannot exceed {MAX_FAMILY_SIZE}."

    return size, None


def validate_language(language: str) -> tuple[str, str | None]:
    """
    Ensure the requested language is in our supported set.

    Returns:
        (language, None) on success or ("English", error_message) on failure.
    """
    if language in SUPPORTED_LANGUAGES:
        return language, None
    return "English", f"Unsupported language '{language}'. Defaulting to English."


def validate_phase(phase: str) -> tuple[str, str | None]:
    """Validate a monsoon phase identifier."""
    if phase in ALLOWED_PHASES:
        return phase, None
    return "", f"Invalid phase '{phase}'. Must be one of: {', '.join(sorted(ALLOWED_PHASES))}."


def validate_housing_type(housing_type: str) -> tuple[str, str | None]:
    """Validate housing type selection."""
    if housing_type in ALLOWED_HOUSING_TYPES:
        return housing_type, None
    return "", (
        f"Invalid housing type '{housing_type}'. "
        f"Must be one of: {', '.join(sorted(ALLOWED_HOUSING_TYPES))}."
    )


def validate_transport_mode(mode: str) -> tuple[str, str | None]:
    """Validate transport mode selection."""
    if mode in ALLOWED_TRANSPORT_MODES:
        return mode, None
    return "", (
        f"Invalid transport mode '{mode}'. "
        f"Must be one of: {', '.join(sorted(ALLOWED_TRANSPORT_MODES))}."
    )


def validate_vulnerabilities(raw_list: list) -> tuple[list[str], str | None]:
    """
    Validate a list of vulnerability strings against the allowed set.
    Unknown entries are silently dropped (no error — avoid leaking allowed values).

    Returns:
        (valid_vulnerabilities, None) always (filtered to safe values).
    """
    if not isinstance(raw_list, list):
        return [], None
    valid = [v for v in raw_list if isinstance(v, str) and v in ALLOWED_VULNERABILITIES]
    return valid, None


def validate_date(date_str: str) -> tuple[str, str | None]:
    """
    Validate a date string in YYYY-MM-DD format.

    Returns:
        (date_str, None) on success or ("", error_message) on failure.
    """
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return "", "Invalid date format. Use YYYY-MM-DD."

    today = date.today()
    if parsed < today:
        return "", "Travel date cannot be in the past."

    # Limit to 30 days ahead (monsoon forecasts beyond that are unreliable)
    max_days = 30
    delta = (parsed - today).days
    if delta > max_days:
        return "", f"Travel date too far ahead. Maximum {max_days} days from today."

    return date_str, None
