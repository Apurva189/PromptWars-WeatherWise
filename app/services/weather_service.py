"""
WeatherWise — Weather Data Service
-------------------------------------
Fetches real-time weather data from the Open-Meteo API (100% free, no API key).
Also uses Open-Meteo's Geocoding API to resolve city names to coordinates.

API docs: https://open-meteo.com/en/docs
Geocoding: https://open-meteo.com/en/docs/geocoding-api
"""

import logging
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── API base URLs ──────────────────────────────────────────────
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# ── HTTP timeout (seconds) ─────────────────────────────────────
_REQUEST_TIMEOUT = 10
_HTTP = requests.Session()

# ── Weather variables to fetch ─────────────────────────────────
_HOURLY_VARS = [
    "precipitation",
    "precipitation_probability",
    "windspeed_10m",
    "relativehumidity_2m",
    "weathercode",
]

# ── WMO Weather interpretation codes relevant to monsoon ──────
_WMO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Heavy drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherService:
    """
    Retrieves current and forecast weather data for a city.
    All methods are stateless and safe to call concurrently.
    """

    def __init__(self) -> None:
        self._city_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._geocode_cache: dict[str, dict] = {}

    def get_weather(self, city: str) -> dict[str, Any]:
        """
        Fetch current weather and 24h precipitation forecast for a city.

        Args:
            city: City name (e.g. 'Mumbai', 'Chennai').

        Returns:
            Dictionary with weather data or an error key.

        Raises:
            ValueError: If the city cannot be found or API fails.
        """
        coords = self._geocode(city)
        if not coords:
            raise ValueError(f"City '{city}' not found. Please check the spelling.")

        raw = self._fetch_forecast(coords["latitude"], coords["longitude"])
        return self._parse_weather(raw, city, coords)

    def search_cities(self, query: str, count: int = 8) -> list[dict[str, Any]]:
        """Return matching places for the city autocomplete UI."""
        key = (query.casefold(), count)
        if key in self._city_cache:
            return [dict(place) for place in self._city_cache[key]]
        try:
            resp = _HTTP.get(
                _GEOCODING_URL,
                params={
                    "name": query,
                    "count": max(1, min(count, 10)),
                    "language": "en",
                    "format": "json",
                },
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            matches = [
                {
                    "name": item.get("name", ""),
                    "admin1": item.get("admin1", ""),
                    "country": item.get("country", ""),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                }
                for item in results
                if item.get("name")
            ]
            self._store_bounded(self._city_cache, key, matches, 128)
            return [dict(place) for place in matches]
        except (requests.RequestException, ValueError) as exc:
            logger.error("City search error for '%s': %s", query, exc)
            return []

    def build_weather_context_string(self, weather_data: dict) -> str:
        """
        Build a concise natural-language weather summary for Gemini prompts.

        Args:
            weather_data: Output from get_weather().

        Returns:
            Single-line summary string.
        """
        if "error" in weather_data:
            return ""

        current = weather_data.get("current", {})
        forecast = weather_data.get("forecast_summary", {})

        parts = [
            f"Location: {weather_data.get('city', 'Unknown')}",
            f"Current: {current.get('description', 'N/A')}",
            f"Temp: {current.get('temperature', 'N/A')}°C",
            f"Humidity: {current.get('humidity', 'N/A')}%",
            f"Wind: {current.get('windspeed', 'N/A')} km/h",
            f"Rain (last hour): {current.get('precipitation', 0)} mm",
            f"24h forecast rain: {forecast.get('total_precipitation_24h', 0):.1f} mm",
            f"Rain probability: {forecast.get('max_rain_probability', 0)}%",
        ]
        return " | ".join(parts)

    # ── Private helpers ───────────────────────────────────────

    def _geocode(self, city: str) -> dict | None:
        """Resolve city name to (latitude, longitude, country)."""
        key = city.casefold()
        if key in self._geocode_cache:
            return dict(self._geocode_cache[key])
        try:
            resp = _HTTP.get(
                _GEOCODING_URL,
                params={"name": city, "count": 1, "language": "en", "format": "json"},
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None
            r = results[0]
            result = {
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "name": r.get("name", city),
                "country": r.get("country", ""),
                "admin1": r.get("admin1", ""),  # State / province
            }
            self._store_bounded(self._geocode_cache, key, result, 256)
            return dict(result)
        except requests.RequestException as exc:
            logger.error("Geocoding error for '%s': %s", city, exc)
            return None

    @staticmethod
    def _store_bounded(cache: dict, key: Any, value: Any, limit: int) -> None:
        """Insert into a small FIFO cache without retaining unbounded input data."""
        if len(cache) >= limit:
            cache.pop(next(iter(cache)))
        cache[key] = value

    def _fetch_forecast(self, lat: float, lon: float) -> dict:
        """Fetch hourly forecast from Open-Meteo."""
        try:
            resp = _HTTP.get(
                _FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": ",".join(_HOURLY_VARS),
                    "current_weather": "true",
                    "timezone": "auto",
                    "forecast_days": 2,
                },
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Weather fetch error (lat=%s lon=%s): %s", lat, lon, exc)
            raise ValueError("Could not fetch weather data. Please try again.") from exc

    def _parse_weather(self, raw: dict, city: str, coords: dict) -> dict:
        """
        Transform raw Open-Meteo response into a clean, UI-ready dict.

        Returns a structured dict with 'current' and 'forecast_summary' keys.
        """
        current_wx = raw.get("current_weather", {})
        hourly = raw.get("hourly", {})

        # ── Current conditions ────────────────────────────────
        wmo_code = int(current_wx.get("weathercode", 0))
        current = {
            "temperature": round(current_wx.get("temperature", 0), 1),
            "windspeed": round(current_wx.get("windspeed", 0), 1),
            "weathercode": wmo_code,
            "description": _WMO_DESCRIPTIONS.get(wmo_code, "Unknown"),
            "is_day": bool(current_wx.get("is_day", 1)),
            # First hour's values for precipitation and humidity
            "precipitation": hourly.get("precipitation", [0])[0],
            "humidity": hourly.get("relativehumidity_2m", [0])[0],
        }

        # ── 24h forecast aggregates ───────────────────────────
        precip_list = hourly.get("precipitation", [])[:24]
        prob_list = hourly.get("precipitation_probability", [])[:24]

        forecast_summary = {
            "total_precipitation_24h": sum(p for p in precip_list if p),
            "max_rain_probability": max((p for p in prob_list if p is not None), default=0),
            "monsoon_alert_level": self._calculate_alert_level(sum(p for p in precip_list if p)),
        }

        return {
            "city": coords.get("name", city),
            "state": coords.get("admin1", ""),
            "country": coords.get("country", ""),
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "current": current,
            "forecast_summary": forecast_summary,
            "updated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 (Python 3.10)
        }

    @staticmethod
    def _calculate_alert_level(total_precip_mm: float) -> str:
        """
        Map 24h forecast precipitation to IMD-style alert levels.

        IMD thresholds (simplified):
          Green  : < 15 mm   — No significant rain
          Yellow : 15-64 mm  — Moderate rain, stay alert
          Orange : 64-115 mm — Heavy rain, be prepared
          Red    : > 115 mm  — Extremely heavy rain, take action
        """
        if total_precip_mm >= 115:
            return "red"
        if total_precip_mm >= 64:
            return "orange"
        if total_precip_mm >= 15:
            return "yellow"
        return "green"
