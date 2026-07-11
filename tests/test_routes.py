"""
WeatherWise — Route Integration Tests
----------------------------------------
Tests all HTTP routes (pages + API endpoints) to verify:
  - Correct status codes
  - Response structure
  - Input validation (400 errors for bad inputs)
  - API endpoint behaviour with mocked AI/weather services

Run with:  pytest tests/test_routes.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.routes import api as api_routes

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    """Create a test Flask application."""
    application = create_app("testing")
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture(scope="function")
def client(app):
    """Return an authenticated test client for the Flask application."""
    cl = app.test_client()
    with cl.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "testuser"
    return cl


# ════════════════════════════════════════════════════════════
# PAGE ROUTES
# ════════════════════════════════════════════════════════════


class TestPageRoutes:
    """Test HTML page-rendering routes."""

    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_brand_name(self, client):
        resp = client.get("/")
        assert b"WeatherWise" in resp.data

    def test_dashboard_returns_200(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200

    def test_dashboard_contains_key_panels(self, client):
        resp = client.get("/dashboard")
        # Check all five panel IDs are present
        for panel in [
            b"panel-chat",
            b"panel-plan",
            b"panel-checklist",
            b"panel-travel",
            b"panel-alerts",
        ]:
            assert panel in resp.data, f"Missing panel: {panel}"

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "WeatherWise"

    def test_404_returns_json(self, client):
        resp = client.get("/non-existent-route")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    @patch("app.routes.api.GeminiService")
    def test_gemini_service_client_is_reused(self, mock_service):
        api_routes._create_gemini_service.cache_clear()

        first = api_routes._create_gemini_service("key", "model")
        second = api_routes._create_gemini_service("key", "model")

        assert first is second
        mock_service.assert_called_once_with(api_key="key", model_name="model")
        api_routes._create_gemini_service.cache_clear()


# ════════════════════════════════════════════════════════════
# WEATHER API
# ════════════════════════════════════════════════════════════


class TestWeatherAPI:
    """Test GET /api/weather endpoint."""

    def test_missing_city_returns_400(self, client):
        resp = client.get("/api/weather?city=")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_invalid_city_chars_returns_400(self, client):
        resp = client.get("/api/weather?city=<script>alert(1)</script>")
        assert resp.status_code == 400

    @patch("app.routes.api.weather_svc")
    def test_valid_city_returns_200(self, mock_weather, client):
        mock_weather.get_weather.return_value = {
            "city": "Mumbai",
            "current": {
                "temperature": 28.0,
                "windspeed": 20.0,
                "description": "Heavy rain",
                "weathercode": 65,
                "is_day": 1,
                "precipitation": 5.2,
                "humidity": 87,
            },
            "forecast_summary": {
                "total_precipitation_24h": 72.0,
                "max_rain_probability": 95,
                "monsoon_alert_level": "orange",
            },
        }
        resp = client.get("/api/weather?city=Mumbai")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["city"] == "Mumbai"
        assert "current" in data
        assert "forecast_summary" in data

    @patch("app.routes.api.weather_svc")
    def test_weather_service_error_returns_400(self, mock_weather, client):
        mock_weather.get_weather.side_effect = ValueError("City not found")
        resp = client.get("/api/weather?city=FakeCity12345")
        assert resp.status_code == 400

    @patch("app.routes.api.weather_svc")
    def test_city_suggestions_returns_matches(self, mock_weather, client):
        mock_weather.search_cities.return_value = [
            {"name": "Mumbai", "admin1": "Maharashtra", "country": "India"}
        ]
        resp = client.get("/api/cities?q=Mum")
        assert resp.status_code == 200
        assert resp.get_json()["suggestions"][0]["name"] == "Mumbai"
        mock_weather.search_cities.assert_called_once_with("Mum")

    def test_city_suggestions_short_query_is_empty(self, client):
        resp = client.get("/api/cities?q=M")
        assert resp.status_code == 200
        assert resp.get_json() == {"suggestions": []}


# ════════════════════════════════════════════════════════════
# CHAT API
# ════════════════════════════════════════════════════════════


class TestChatAPI:
    """Test POST /api/chat endpoint."""

    def _post(self, client, payload):
        return client.post(
            "/api/chat",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_empty_message_returns_400(self, client):
        resp = self._post(client, {"message": ""})
        assert resp.status_code == 400

    def test_missing_message_returns_400(self, client):
        resp = self._post(client, {})
        assert resp.status_code == 400

    def test_oversized_message_returns_400(self, client):
        long_msg = "A" * 501
        resp = self._post(client, {"message": long_msg})
        assert resp.status_code == 400

    @patch("app.routes.api._get_gemini_service")
    @patch("app.routes.api.weather_svc")
    def test_valid_message_returns_reply(self, mock_weather, mock_gemini_fn, client):
        mock_weather.get_weather.side_effect = ValueError("unavailable")
        mock_svc = MagicMock()
        mock_svc.chat.return_value = ("Stay safe during monsoon!", [])
        mock_gemini_fn.return_value = mock_svc

        resp = self._post(client, {"message": "What should I do during a flood?"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reply" in data
        assert data["reply"] == "Stay safe during monsoon!"

    def test_chat_reset_clears_session(self, client):
        resp = client.post("/api/chat/reset")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data


# ════════════════════════════════════════════════════════════
# PREPAREDNESS PLAN API
# ════════════════════════════════════════════════════════════


class TestPlanAPI:
    """Test POST /api/preparedness-plan endpoint."""

    def _post(self, client, payload):
        return client.post(
            "/api/preparedness-plan",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_missing_location_returns_400(self, client):
        resp = self._post(client, {"location": ""})
        assert resp.status_code == 400

    def test_invalid_phase_returns_400(self, client):
        resp = self._post(client, {"location": "Mumbai", "phase": "invalid-phase"})
        assert resp.status_code == 400

    def test_invalid_family_size_returns_400(self, client):
        resp = self._post(client, {"location": "Mumbai", "family_size": -1})
        assert resp.status_code == 400

    @patch("app.routes.api._get_gemini_service")
    @patch("app.routes.api._try_get_weather_context", return_value="")
    def test_valid_request_returns_plan(self, _mock_weather, mock_gemini_fn, client):
        mock_svc = MagicMock()
        mock_svc.generate_preparedness_plan.return_value = "## Your Plan\n- Stay safe"
        mock_gemini_fn.return_value = mock_svc

        resp = self._post(
            client,
            {
                "location": "Mumbai",
                "family_size": 4,
                "phase": "active-monsoon",
                "vulnerabilities": ["elderly"],
                "language": "English",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "plan" in data


# ════════════════════════════════════════════════════════════
# CHECKLIST API
# ════════════════════════════════════════════════════════════


class TestChecklistAPI:
    """Test POST /api/checklist endpoint."""

    def _post(self, client, payload):
        return client.post(
            "/api/checklist",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_invalid_housing_type_returns_400(self, client):
        resp = self._post(client, {"location": "Chennai", "housing_type": "castle"})
        assert resp.status_code == 400

    @patch("app.routes.api._get_gemini_service")
    def test_valid_request_returns_checklist(self, mock_gemini_fn, client):
        mock_svc = MagicMock()
        mock_svc.generate_checklist.return_value = "## Checklist\n- Water"
        mock_gemini_fn.return_value = mock_svc

        resp = self._post(
            client,
            {
                "location": "Chennai",
                "housing_type": "apartment",
                "family_size": 3,
            },
        )
        assert resp.status_code == 200
        assert "checklist" in resp.get_json()


# ════════════════════════════════════════════════════════════
# TRAVEL ADVISORY API
# ════════════════════════════════════════════════════════════


class TestTravelAPI:
    """Test POST /api/travel-advisory endpoint."""

    def _post(self, client, payload):
        return client.post(
            "/api/travel-advisory",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_past_date_returns_400(self, client):
        resp = self._post(
            client,
            {
                "origin": "Bangalore",
                "destination": "Coorg",
                "travel_date": "2020-01-01",
                "transport_mode": "car",
            },
        )
        assert resp.status_code == 400

    def test_invalid_transport_mode_returns_400(self, client):
        from datetime import date, timedelta

        future = (date.today() + timedelta(days=3)).isoformat()
        resp = self._post(
            client,
            {
                "origin": "Bangalore",
                "destination": "Coorg",
                "travel_date": future,
                "transport_mode": "rocket",
            },
        )
        assert resp.status_code == 400

    @patch("app.routes.api._get_gemini_service")
    def test_valid_request_returns_advisory(self, mock_gemini_fn, client):
        from datetime import date, timedelta

        future = (date.today() + timedelta(days=3)).isoformat()

        mock_svc = MagicMock()
        mock_svc.generate_travel_advisory.return_value = "⚠️ High risk route"
        mock_gemini_fn.return_value = mock_svc

        resp = self._post(
            client,
            {
                "origin": "Bangalore",
                "destination": "Mysore",
                "travel_date": future,
                "transport_mode": "car",
            },
        )
        assert resp.status_code == 200
        assert "advisory" in resp.get_json()


# ════════════════════════════════════════════════════════════
# ALERTS API
# ════════════════════════════════════════════════════════════


class TestAlertsAPI:
    """Test POST /api/alerts endpoint."""

    def _post(self, client, payload):
        return client.post(
            "/api/alerts",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_invalid_phase_returns_400(self, client):
        resp = self._post(client, {"location": "Kolkata", "phase": "unknown"})
        assert resp.status_code == 400

    @patch("app.routes.api._get_gemini_service")
    @patch("app.routes.api._try_get_weather_context", return_value="")
    def test_valid_request_returns_alerts(self, _mock_w, mock_gemini_fn, client):
        mock_svc = MagicMock()
        mock_svc.generate_alerts.return_value = "🔴 RED ALERT — Heavy flooding"
        mock_gemini_fn.return_value = mock_svc

        resp = self._post(client, {"location": "Kolkata", "phase": "during"})
        assert resp.status_code == 200
        assert "alerts" in resp.get_json()
