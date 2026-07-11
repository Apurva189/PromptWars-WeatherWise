"""
WeatherWise — Service Unit Tests
-----------------------------------
Tests the GeminiService and WeatherService classes in isolation
using unittest.mock to avoid actual API calls.

Run with:  pytest tests/test_services.py -v
"""

from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from app.services.gemini_service import GeminiService
from app.services.weather_service import WeatherService


# ════════════════════════════════════════════════════════════
# GeminiService Tests
# ════════════════════════════════════════════════════════════

class TestGeminiService:
    """Unit tests for GeminiService."""

    @pytest.fixture
    def mock_model(self):
        """Return a mocked GenerativeModel instance."""
        with patch("app.services.gemini_service.genai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model
            yield mock_model

    def _make_response(self, text: str) -> MagicMock:
        """Create a mock Gemini response object."""
        resp = MagicMock()
        type(resp).text = PropertyMock(return_value=text)
        return resp

    # ── Initialisation ────────────────────────────────────

    def test_raises_without_api_key(self):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiService(api_key="")

    def test_raises_with_none_api_key(self):
        with pytest.raises(ValueError):
            GeminiService(api_key=None)

    # ── Chat ──────────────────────────────────────────────

    def test_chat_returns_reply_and_history(self, mock_model):
        # Mock chat session
        mock_session = MagicMock()
        response = self._make_response("Stay safe during floods!")
        mock_session.send_message.return_value = response
        # history after chat
        mock_content = MagicMock()
        mock_content.role = "user"
        part = MagicMock()
        part.text = "Hello"
        mock_content.parts = [part]
        mock_session.history = [mock_content]
        mock_model.start_chat.return_value = mock_session

        svc = GeminiService(api_key="fake-key")
        reply, history = svc.chat(
            user_message="What to do in a flood?",
            history=[],
            language="English",
        )

        assert reply == "Stay safe during floods!"
        assert isinstance(history, list)

    def test_chat_passes_weather_context(self, mock_model):
        mock_session = MagicMock()
        response = self._make_response("AI response with context")
        mock_session.send_message.return_value = response
        mock_session.history = []
        mock_model.start_chat.return_value = mock_session

        svc = GeminiService(api_key="fake-key")
        svc.chat(
            user_message="Is it safe?",
            history=[],
            language="Hindi",
            weather_context="Heavy rain in Mumbai",
        )

        # Verify message sent to model contains the weather context
        call_args = mock_session.send_message.call_args[0][0]
        assert "Heavy rain in Mumbai" in call_args

    def test_chat_gemini_error_raises_value_error(self, mock_model):
        mock_session = MagicMock()
        mock_session.send_message.side_effect = RuntimeError("API quota exceeded")
        mock_model.start_chat.return_value = mock_session

        svc = GeminiService(api_key="fake-key")
        with pytest.raises(ValueError, match="AI service error"):
            svc.chat("Test", [])

    # ── Preparedness Plan ─────────────────────────────────

    def test_generate_plan_calls_generate_content(self, mock_model):
        mock_model.generate_content.return_value = self._make_response("## Plan\n- Action 1")

        svc = GeminiService(api_key="fake-key")
        result = svc.generate_preparedness_plan(
            location="Mumbai",
            family_size=4,
            vulnerabilities=["elderly"],
            phase="active-monsoon",
            language="English",
        )

        assert "Plan" in result
        mock_model.generate_content.assert_called_once()

    def test_generate_plan_includes_location_in_prompt(self, mock_model):
        mock_model.generate_content.return_value = self._make_response("Plan text")

        svc = GeminiService(api_key="fake-key")
        svc.generate_preparedness_plan("Kolkata", 3, [], "before")

        prompt = mock_model.generate_content.call_args[0][0]
        assert "Kolkata" in prompt

    # ── Checklist ─────────────────────────────────────────

    def test_generate_checklist_returns_string(self, mock_model):
        mock_model.generate_content.return_value = self._make_response("## Checklist\n- Water bottles")

        svc = GeminiService(api_key="fake-key")
        result = svc.generate_checklist("Chennai", "apartment", 3, "Tamil")

        assert isinstance(result, str)
        assert "Checklist" in result

    # ── Travel Advisory ───────────────────────────────────

    def test_generate_travel_advisory_includes_route(self, mock_model):
        mock_model.generate_content.return_value = self._make_response("Advisory content")

        svc = GeminiService(api_key="fake-key")
        svc.generate_travel_advisory("Bangalore", "Coorg", "2025-08-15", "car")

        prompt = mock_model.generate_content.call_args[0][0]
        assert "Bangalore" in prompt
        assert "Coorg" in prompt

    # ── Alerts ────────────────────────────────────────────

    def test_generate_alerts_includes_phase(self, mock_model):
        mock_model.generate_content.return_value = self._make_response("🔴 RED ALERT")

        svc = GeminiService(api_key="fake-key")
        svc.generate_alerts("Mumbai", "during", "English")

        prompt = mock_model.generate_content.call_args[0][0]
        assert "during" in prompt.lower() or "active" in prompt.lower()

    # ── Safety response fallback ──────────────────────────

    def test_blocked_response_returns_safe_fallback(self, mock_model):
        """When Gemini blocks a response, we should get a safe fallback string."""
        bad_response = MagicMock()
        type(bad_response).text = PropertyMock(side_effect=ValueError("Blocked"))
        mock_model.generate_content.return_value = bad_response

        svc = GeminiService(api_key="fake-key")
        result = svc.generate_checklist("Mumbai", "apartment", 2)

        assert isinstance(result, str)
        assert len(result) > 0  # Should return fallback text


# ════════════════════════════════════════════════════════════
# WeatherService Tests
# ════════════════════════════════════════════════════════════

class TestWeatherService:
    """Unit tests for WeatherService."""

    MOCK_GEOCODE_RESPONSE = {
        "results": [{
            "latitude": 19.076,
            "longitude": 72.877,
            "name": "Mumbai",
            "country": "India",
            "admin1": "Maharashtra",
        }]
    }

    MOCK_FORECAST_RESPONSE = {
        "current_weather": {
            "temperature": 28.5,
            "windspeed": 22.0,
            "weathercode": 63,
            "is_day": 1,
        },
        "hourly": {
            "time": ["2025-07-15T00:00"] * 48,
            "precipitation": [5.0] * 48,
            "precipitation_probability": [80] * 48,
            "windspeed_10m": [20.0] * 48,
            "relativehumidity_2m": [85] * 48,
            "weathercode": [63] * 48,
        }
    }

    @pytest.fixture
    def svc(self):
        return WeatherService()

    @patch("app.services.weather_service.requests.get")
    def test_get_weather_returns_correct_structure(self, mock_get, svc):
        # First call: geocoding, second call: forecast
        geocode_resp = MagicMock()
        geocode_resp.json.return_value = self.MOCK_GEOCODE_RESPONSE
        geocode_resp.raise_for_status = MagicMock()

        forecast_resp = MagicMock()
        forecast_resp.json.return_value = self.MOCK_FORECAST_RESPONSE
        forecast_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [geocode_resp, forecast_resp]

        data = svc.get_weather("Mumbai")

        assert data["city"] == "Mumbai"
        assert "current" in data
        assert "forecast_summary" in data
        assert data["current"]["temperature"] == 28.5

    @patch("app.services.weather_service.requests.get")
    def test_unknown_city_raises_value_error(self, mock_get, svc):
        no_results_resp = MagicMock()
        no_results_resp.json.return_value = {"results": []}
        no_results_resp.raise_for_status = MagicMock()
        mock_get.return_value = no_results_resp

        with pytest.raises(ValueError, match="not found"):
            svc.get_weather("FakeNonExistentCity999")

    @patch("app.services.weather_service.requests.get")
    def test_search_cities_returns_multiple_matches(self, mock_get, svc):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "results": [
                {
                    "name": "Mumbai",
                    "admin1": "Maharashtra",
                    "country": "India",
                    "latitude": 19.076,
                    "longitude": 72.877,
                },
                {
                    "name": "Mumbwa",
                    "admin1": "Central Province",
                    "country": "Zambia",
                    "latitude": -14.98,
                    "longitude": 27.06,
                },
            ]
        }
        mock_get.return_value = response

        matches = svc.search_cities("Mum")

        assert len(matches) == 2
        assert matches[0]["name"] == "Mumbai"
        assert mock_get.call_args.kwargs["params"]["count"] == 8

    def test_alert_level_calculation(self, svc):
        """Verify IMD-style alert level thresholds."""
        assert svc._calculate_alert_level(0)    == "green"
        assert svc._calculate_alert_level(14.9) == "green"
        assert svc._calculate_alert_level(15)   == "yellow"
        assert svc._calculate_alert_level(63.9) == "yellow"
        assert svc._calculate_alert_level(64)   == "orange"
        assert svc._calculate_alert_level(114.9)== "orange"
        assert svc._calculate_alert_level(115)  == "red"
        assert svc._calculate_alert_level(200)  == "red"

    @patch("app.services.weather_service.requests.get")
    def test_build_weather_context_string(self, mock_get, svc):
        geocode_resp = MagicMock()
        geocode_resp.json.return_value = self.MOCK_GEOCODE_RESPONSE
        geocode_resp.raise_for_status = MagicMock()

        forecast_resp = MagicMock()
        forecast_resp.json.return_value = self.MOCK_FORECAST_RESPONSE
        forecast_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [geocode_resp, forecast_resp]

        data = svc.get_weather("Mumbai")
        context = svc.build_weather_context_string(data)

        assert "Mumbai" in context
        assert "°C" in context or "28.5" in context

    def test_build_weather_context_empty_on_error(self, svc):
        """If weather data has an error key, context string should be empty."""
        result = svc.build_weather_context_string({"error": "Not found"})
        assert result == ""
