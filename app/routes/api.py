"""
WeatherWise — API Routes (AI-Powered Endpoints)
-------------------------------------------------
All endpoints validate inputs, call the appropriate service, and return JSON.

Rate limits are applied per endpoint using Flask-Limiter decorators.
Rate limit strategy: 10 AI calls / minute per IP (protects Gemini API quota).

Error handling pattern:
  - ValueError → 400 Bad Request (validation or AI errors)
  - Unexpected Exception → 500 Internal Server Error (logged, generic message to client)
"""

import logging
from functools import lru_cache

from flask import Blueprint, current_app, jsonify, request, session

from app import limiter
from app.services.gemini_service import GeminiService
from app.services.weather_service import WeatherService
from app.utils.auth import login_required
from app.utils.validators import (
    sanitise_city,
    sanitise_text,
    validate_date,
    validate_family_size,
    validate_housing_type,
    validate_language,
    validate_phase,
    validate_transport_mode,
    validate_vulnerabilities,
)

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)

# ── Shared service instances ──────────────────────────────────
# WeatherService is stateless, so one instance is fine for the whole app.
weather_svc = WeatherService()


def _get_gemini_service() -> GeminiService:
    """
    Lazily create a GeminiService using the current app's config.
    Called inside every route so we always have a live app context.
    """
    api_key = current_app.config.get("GEMINI_API_KEY")
    model = current_app.config.get("GEMINI_MODEL", "gemini-3.5-flash")
    return _create_gemini_service(api_key, model)


@lru_cache(maxsize=4)
def _create_gemini_service(api_key: str, model: str) -> GeminiService:
    """Reuse the SDK client and its HTTP connection pool within each worker."""
    return GeminiService(api_key=api_key, model_name=model)


def _json_error(message: str, status: int = 400):
    """Helper — return a consistent JSON error response."""
    return jsonify({"error": message}), status


# ─────────────────────────────────────────────────────────────
# Weather endpoint (no AI — just fetches Open-Meteo data)
# ─────────────────────────────────────────────────────────────


@api_bp.route("/weather", methods=["GET"])
@limiter.limit("30 per minute")
@login_required
def get_weather():
    """
    GET /api/weather?city=Mumbai

    Returns current weather and 24h forecast for the given city.
    """
    city_raw = request.args.get("city", "").strip()
    city, err = sanitise_city(city_raw)
    if err:
        return _json_error(err)

    try:
        data = weather_svc.get_weather(city)
        return jsonify(data), 200
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in get_weather: %s", exc)
        return _json_error("Could not fetch weather data.", 500)


@api_bp.route("/cities", methods=["GET"])
@limiter.limit("60 per minute")
@login_required
def search_cities():
    """GET /api/cities?q=Mum — return geocoding suggestions."""
    query_raw = request.args.get("q", "").strip()
    if len(query_raw) < 2:
        return jsonify({"suggestions": []}), 200

    query, err = sanitise_city(query_raw)
    if err:
        return _json_error(err)

    return jsonify({"suggestions": weather_svc.search_cities(query)}), 200


# ─────────────────────────────────────────────────────────────
# Chat endpoint
# ─────────────────────────────────────────────────────────────


@api_bp.route("/chat", methods=["POST"])
@limiter.limit("10 per minute")
@login_required
def chat():
    """
    POST /api/chat
    Body: { "message": "...", "language": "Hindi", "city": "Mumbai" }

    Maintains conversation history in the server-side Flask session.
    """
    data = request.get_json(silent=True) or {}

    message_raw = data.get("message", "")
    message, err = sanitise_text(message_raw)
    if err:
        return _json_error(err)

    language, _ = validate_language(data.get("language", "English"))

    # Optionally fetch live weather to ground the AI response
    weather_context = ""
    city_raw = data.get("city", "")
    if city_raw:
        city, city_err = sanitise_city(city_raw)
        if not city_err:
            try:
                w_data = weather_svc.get_weather(city)
                weather_context = weather_svc.build_weather_context_string(w_data)
            except Exception:
                pass  # Weather is optional — don't fail the chat if it's unavailable

    # Retrieve existing chat history from session (persists across requests)
    history = session.get("chat_history", [])

    try:
        gemini = _get_gemini_service()
        reply, updated_history = gemini.chat(message, history, language, weather_context)
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in chat: %s", exc)
        return _json_error("AI service temporarily unavailable.", 500)

    # Persist updated history — Flask session is limited to ~4 KB by default
    # Keep only the last 20 turns to avoid session overflow
    session["chat_history"] = updated_history[-20:]
    session.modified = True

    return jsonify({"reply": reply}), 200


@api_bp.route("/chat/reset", methods=["POST"])
@login_required
def reset_chat():
    """POST /api/chat/reset — Clear conversation history from session."""
    session.pop("chat_history", None)
    session.modified = True
    return jsonify({"message": "Conversation reset."}), 200


# ─────────────────────────────────────────────────────────────
# Preparedness Plan endpoint
# ─────────────────────────────────────────────────────────────


@api_bp.route("/preparedness-plan", methods=["POST"])
@limiter.limit("10 per minute")
@login_required
def preparedness_plan():
    """
    POST /api/preparedness-plan
    Body: {
        "location": "Pune",
        "family_size": 4,
        "vulnerabilities": ["elderly", "infant"],
        "phase": "active-monsoon",
        "language": "English"
    }
    """
    data = request.get_json(silent=True) or {}

    location, err = sanitise_city(data.get("location", ""))
    if err:
        return _json_error(f"Location: {err}")

    family_size, err = validate_family_size(data.get("family_size", 1))
    if err:
        return _json_error(err)

    vulnerabilities, _ = validate_vulnerabilities(data.get("vulnerabilities", []))

    phase, err = validate_phase(data.get("phase", "active-monsoon"))
    if err:
        return _json_error(err)

    language, _ = validate_language(data.get("language", "English"))

    # Optionally enrich prompt with live weather
    weather_context = _try_get_weather_context(location)

    try:
        gemini = _get_gemini_service()
        plan = gemini.generate_preparedness_plan(
            location, family_size, vulnerabilities, phase, language, weather_context
        )
        return jsonify({"plan": plan}), 200
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Error generating preparedness plan: %s", exc)
        return _json_error("Could not generate plan. Please try again.", 500)


# ─────────────────────────────────────────────────────────────
# Emergency Checklist endpoint
# ─────────────────────────────────────────────────────────────


@api_bp.route("/checklist", methods=["POST"])
@limiter.limit("10 per minute")
@login_required
def checklist():
    """
    POST /api/checklist
    Body: {
        "location": "Chennai",
        "housing_type": "apartment",
        "family_size": 3,
        "language": "Tamil"
    }
    """
    data = request.get_json(silent=True) or {}

    location, err = sanitise_city(data.get("location", ""))
    if err:
        return _json_error(f"Location: {err}")

    housing_type, err = validate_housing_type(data.get("housing_type", "apartment"))
    if err:
        return _json_error(err)

    family_size, err = validate_family_size(data.get("family_size", 1))
    if err:
        return _json_error(err)

    language, _ = validate_language(data.get("language", "English"))

    try:
        gemini = _get_gemini_service()
        result = gemini.generate_checklist(location, housing_type, family_size, language)
        return jsonify({"checklist": result}), 200
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Error generating checklist: %s", exc)
        return _json_error("Could not generate checklist. Please try again.", 500)


# ─────────────────────────────────────────────────────────────
# Travel Advisory endpoint
# ─────────────────────────────────────────────────────────────


@api_bp.route("/travel-advisory", methods=["POST"])
@limiter.limit("10 per minute")
@login_required
def travel_advisory():
    """
    POST /api/travel-advisory
    Body: {
        "origin": "Bangalore",
        "destination": "Coorg",
        "travel_date": "2025-08-15",
        "transport_mode": "car",
        "language": "English"
    }
    """
    data = request.get_json(silent=True) or {}

    origin, err = sanitise_city(data.get("origin", ""))
    if err:
        return _json_error(f"Origin: {err}")

    destination, err = sanitise_city(data.get("destination", ""))
    if err:
        return _json_error(f"Destination: {err}")

    travel_date, err = validate_date(data.get("travel_date", ""))
    if err:
        return _json_error(err)

    transport_mode, err = validate_transport_mode(data.get("transport_mode", "car"))
    if err:
        return _json_error(err)

    language, _ = validate_language(data.get("language", "English"))

    try:
        gemini = _get_gemini_service()
        advisory = gemini.generate_travel_advisory(
            origin, destination, travel_date, transport_mode, language
        )
        return jsonify({"advisory": advisory}), 200
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Error generating travel advisory: %s", exc)
        return _json_error("Could not generate advisory. Please try again.", 500)


# ─────────────────────────────────────────────────────────────
# Alerts endpoint
# ─────────────────────────────────────────────────────────────


@api_bp.route("/alerts", methods=["POST"])
@limiter.limit("10 per minute")
@login_required
def alerts():
    """
    POST /api/alerts
    Body: {
        "location": "Kolkata",
        "phase": "during",
        "language": "Bengali"
    }
    """
    data = request.get_json(silent=True) or {}

    location, err = sanitise_city(data.get("location", ""))
    if err:
        return _json_error(f"Location: {err}")

    phase, err = validate_phase(data.get("phase", "during"))
    if err:
        return _json_error(err)

    language, _ = validate_language(data.get("language", "English"))

    weather_context = _try_get_weather_context(location)

    try:
        gemini = _get_gemini_service()
        result = gemini.generate_alerts(location, phase, language, weather_context)
        return jsonify({"alerts": result}), 200
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("Error generating alerts: %s", exc)
        return _json_error("Could not generate alerts. Please try again.", 500)


# ─────────────────────────────────────────────────────────────
# Private helper
# ─────────────────────────────────────────────────────────────


def _try_get_weather_context(city: str) -> str:
    """
    Silently attempt to fetch live weather context for a city.
    Returns empty string on any failure — weather grounding is optional.
    """
    try:
        data = weather_svc.get_weather(city)
        return weather_svc.build_weather_context_string(data)
    except Exception:
        return ""
