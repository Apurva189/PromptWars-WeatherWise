"""
WeatherWise — Validator Unit Tests
-------------------------------------
Tests every public function in app/utils/validators.py including:
  - Normal inputs
  - Edge cases (empty, boundary values)
  - XSS injection payloads
  - Type mismatches

Run with:  pytest tests/test_validators.py -v
"""

import pytest
from datetime import date, timedelta

from app.utils.validators import (
    sanitise_text,
    sanitise_city,
    validate_family_size,
    validate_language,
    validate_phase,
    validate_housing_type,
    validate_transport_mode,
    validate_vulnerabilities,
    validate_date,
    MAX_TEXT_LENGTH,
    MAX_CITY_LENGTH,
    MAX_FAMILY_SIZE,
    MIN_FAMILY_SIZE,
)


# ════════════════════════════════════════════════════════════
# sanitise_text
# ════════════════════════════════════════════════════════════

class TestSanitiseText:

    def test_valid_text_passes(self):
        text, err = sanitise_text("What should I do during a flood?")
        assert err is None
        assert text == "What should I do during a flood?"

    def test_strips_leading_trailing_whitespace(self):
        text, err = sanitise_text("  hello  ")
        assert err is None
        assert text == "hello"

    def test_empty_string_returns_error(self):
        _, err = sanitise_text("")
        assert err is not None

    def test_whitespace_only_returns_error(self):
        _, err = sanitise_text("   ")
        assert err is not None

    def test_xss_script_tag_is_escaped(self):
        text, err = sanitise_text("<script>alert('xss')</script>")
        assert err is None
        # The angle brackets should NOT appear literally
        assert "<script>" not in text
        assert "alert" in text  # The text content should remain

    def test_xss_img_payload_is_escaped(self):
        text, err = sanitise_text('<img src=x onerror="alert(1)">')
        assert err is None
        assert "<img" not in text

    def test_oversized_input_returns_error(self):
        long = "A" * (MAX_TEXT_LENGTH + 1)
        _, err = sanitise_text(long)
        assert err is not None
        assert "long" in err.lower() or "maximum" in err.lower()

    def test_exactly_max_length_passes(self):
        text = "B" * MAX_TEXT_LENGTH
        result, err = sanitise_text(text)
        assert err is None

    def test_null_bytes_removed(self):
        text, err = sanitise_text("hello\x00world")
        assert err is None
        assert "\x00" not in text

    def test_non_string_input_returns_error(self):
        _, err = sanitise_text(12345)
        assert err is not None


# ════════════════════════════════════════════════════════════
# sanitise_city
# ════════════════════════════════════════════════════════════

class TestSanitiseCity:

    def test_valid_indian_city_passes(self):
        city, err = sanitise_city("Mumbai")
        assert err is None
        assert city == "Mumbai"

    def test_city_with_hyphen_passes(self):
        city, err = sanitise_city("New Delhi")
        assert err is None

    def test_city_with_apostrophe_passes(self):
        city, err = sanitise_city("Hubli-Dharwad")
        assert err is None

    def test_empty_city_returns_error(self):
        _, err = sanitise_city("")
        assert err is not None

    def test_xss_in_city_returns_error(self):
        _, err = sanitise_city("<script>alert(1)</script>")
        assert err is not None

    def test_sql_injection_attempt_returns_error(self):
        _, err = sanitise_city("Mumbai'; DROP TABLE cities;--")
        assert err is not None

    def test_oversized_city_returns_error(self):
        _, err = sanitise_city("C" * (MAX_CITY_LENGTH + 1))
        assert err is not None

    def test_strips_whitespace(self):
        city, err = sanitise_city("  Pune  ")
        assert err is None
        assert city == "Pune"


# ════════════════════════════════════════════════════════════
# validate_family_size
# ════════════════════════════════════════════════════════════

class TestValidateFamilySize:

    def test_valid_integer_passes(self):
        size, err = validate_family_size(4)
        assert err is None
        assert size == 4

    def test_string_integer_passes(self):
        size, err = validate_family_size("5")
        assert err is None
        assert size == 5

    def test_zero_returns_error(self):
        _, err = validate_family_size(0)
        assert err is not None

    def test_negative_returns_error(self):
        _, err = validate_family_size(-1)
        assert err is not None

    def test_above_max_returns_error(self):
        _, err = validate_family_size(MAX_FAMILY_SIZE + 1)
        assert err is not None

    def test_exactly_max_passes(self):
        size, err = validate_family_size(MAX_FAMILY_SIZE)
        assert err is None

    def test_non_numeric_returns_error(self):
        _, err = validate_family_size("abc")
        assert err is not None

    def test_float_rounds_down(self):
        # int("3.5") raises ValueError, but int(3.5) = 3 — test the actual behaviour
        size, err = validate_family_size(3.5)
        assert err is None
        assert size == 3


# ════════════════════════════════════════════════════════════
# validate_language
# ════════════════════════════════════════════════════════════

class TestValidateLanguage:

    def test_english_passes(self):
        lang, err = validate_language("English")
        assert err is None
        assert lang == "English"

    def test_hindi_passes(self):
        lang, err = validate_language("Hindi")
        assert err is None

    @pytest.mark.parametrize("lang", [
        "Bengali", "Tamil", "Telugu", "Marathi",
        "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia", "Urdu"
    ])
    def test_all_supported_languages_pass(self, lang):
        result, err = validate_language(lang)
        assert err is None
        assert result == lang

    def test_unsupported_language_returns_english_default(self):
        lang, err = validate_language("Klingon")
        assert lang == "English"
        assert err is not None

    def test_empty_string_defaults_to_english(self):
        lang, err = validate_language("")
        assert lang == "English"


# ════════════════════════════════════════════════════════════
# validate_phase
# ════════════════════════════════════════════════════════════

class TestValidatePhase:

    @pytest.mark.parametrize("phase", [
        "pre-monsoon", "active-monsoon", "post-monsoon",
        "before", "during", "after"
    ])
    def test_valid_phases_pass(self, phase):
        result, err = validate_phase(phase)
        assert err is None
        assert result == phase

    def test_invalid_phase_returns_error(self):
        _, err = validate_phase("never")
        assert err is not None

    def test_empty_phase_returns_error(self):
        _, err = validate_phase("")
        assert err is not None


# ════════════════════════════════════════════════════════════
# validate_housing_type
# ════════════════════════════════════════════════════════════

class TestValidateHousingType:

    def test_apartment_passes(self):
        result, err = validate_housing_type("apartment")
        assert err is None

    def test_independent_house_passes(self):
        result, err = validate_housing_type("independent-house")
        assert err is None

    def test_rural_home_passes(self):
        result, err = validate_housing_type("rural-home")
        assert err is None

    def test_invalid_type_returns_error(self):
        _, err = validate_housing_type("castle")
        assert err is not None


# ════════════════════════════════════════════════════════════
# validate_transport_mode
# ════════════════════════════════════════════════════════════

class TestValidateTransportMode:

    @pytest.mark.parametrize("mode", ["car", "bike", "bus", "train", "flight", "walk"])
    def test_valid_modes_pass(self, mode):
        result, err = validate_transport_mode(mode)
        assert err is None

    def test_invalid_mode_returns_error(self):
        _, err = validate_transport_mode("hovercraft")
        assert err is not None


# ════════════════════════════════════════════════════════════
# validate_vulnerabilities
# ════════════════════════════════════════════════════════════

class TestValidateVulnerabilities:

    def test_valid_vulnerabilities_pass(self):
        result, err = validate_vulnerabilities(["elderly", "infant"])
        assert err is None
        assert set(result) == {"elderly", "infant"}

    def test_unknown_vulnerabilities_silently_dropped(self):
        result, err = validate_vulnerabilities(["elderly", "dragon", "robot"])
        assert err is None
        assert "dragon" not in result
        assert "robot" not in result
        assert "elderly" in result

    def test_empty_list_passes(self):
        result, err = validate_vulnerabilities([])
        assert err is None
        assert result == []

    def test_non_list_returns_empty(self):
        result, err = validate_vulnerabilities("elderly")
        assert err is None
        assert result == []

    def test_xss_payload_is_filtered(self):
        result, err = validate_vulnerabilities(["<script>", "elderly"])
        assert err is None
        assert "<script>" not in result


# ════════════════════════════════════════════════════════════
# validate_date
# ════════════════════════════════════════════════════════════

class TestValidateDate:

    def test_future_date_passes(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        result, err = validate_date(future)
        assert err is None
        assert result == future

    def test_past_date_returns_error(self):
        past = "2020-01-01"
        _, err = validate_date(past)
        assert err is not None
        assert "past" in err.lower()

    def test_invalid_format_returns_error(self):
        _, err = validate_date("15-07-2025")
        assert err is not None

    def test_too_far_future_returns_error(self):
        far_future = (date.today() + timedelta(days=31)).isoformat()
        _, err = validate_date(far_future)
        assert err is not None

    def test_exactly_30_days_ahead_passes(self):
        just_valid = (date.today() + timedelta(days=30)).isoformat()
        result, err = validate_date(just_valid)
        assert err is None

    def test_empty_string_returns_error(self):
        _, err = validate_date("")
        assert err is not None

    def test_none_returns_error(self):
        _, err = validate_date(None)
        assert err is not None
