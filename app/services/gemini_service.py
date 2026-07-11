"""
WeatherWise — Gemini AI Service
----------------------------------
Abstracts all interactions with the Google Gemini API.
Each public method corresponds to one AI-powered feature in the app.

Design decisions:
  - One GeminiService instance is reused per worker to preserve HTTP connections
  - Chat history is stored as a plain list of dicts so it serialises cleanly
    into Flask's session (which uses JSON under the hood)
  - All prompts are built via private helper methods to keep prompt engineering
    centralised and easy to iterate on
  - Errors from the Gemini SDK are caught and re-raised as plain ValueError so
    route handlers don't need to import Gemini-specific exceptions
"""

import logging
from typing import Any

from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

# ── Safety settings — applied to every API call ───────────────
_SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"
    ),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
]

# ── System instruction shared by all AI calls ─────────────────
_SYSTEM_INSTRUCTION = """You are WeatherWise, an expert AI assistant specialising in monsoon preparedness, 
disaster risk reduction, and citizen safety in India. Your knowledge covers:
- Indian Meteorological Department (IMD) guidelines and alert colour codes
- State Disaster Management Authority (SDMA) protocols
- First-aid and emergency response during floods, landslides, and cyclones
- Home & infrastructure protection during heavy rainfall
- Safe travel during monsoon conditions
- Community coordination and evacuation procedures

Rules you MUST follow:
1. Always prioritise human safety. If the situation sounds life-threatening, tell users to contact 
   emergency services (NDRF: 011-24363260, SDRF, local police: 100, ambulance: 108) FIRST.
2. Give practical, actionable advice — not generic disclaimers.
3. Respond in the language the user requests (see language tag at the end of messages).
4. Keep responses clear and structured. Use bullet points and short paragraphs.
5. For emergency checklists and plans, use numbered lists with categories.
6. Do NOT make up specific forecast data; if weather data is provided, use it. Otherwise, give general monsoon guidance.
7. Acknowledge uncertainty honestly."""


class GeminiService:
    """
    Wraps the Google Gemini generative AI SDK.

    Args:
        api_key: Google Gemini API key.
        model_name: Gemini model identifier (e.g. 'gemini-3.5-flash').
    """

    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash") -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required but not set.")
        self._client = genai.Client(api_key=api_key)
        self._config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            safety_settings=_SAFETY_SETTINGS,
        )
        self._model_name = model_name

    # ── Public AI feature methods ─────────────────────────────

    def chat(
        self,
        user_message: str,
        history: list[dict],
        language: str = "English",
        weather_context: str = "",
    ) -> tuple[str, list[dict]]:
        """
        Send a message in a conversational session.

        Args:
            user_message: The user's latest message.
            history: Serialised chat history (list of {role, parts} dicts).
            language: Response language (e.g. 'Hindi', 'Tamil').
            weather_context: Optional live weather summary to ground the AI.

        Returns:
            Tuple of (AI response text, updated history list).
        """
        # Append weather context and language tag to the user message
        full_message = self._build_chat_message(user_message, language, weather_context)
        contents = list(history or [])
        contents.append({"role": "user", "parts": [{"text": full_message}]})

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=self._config,
            )
            reply_text = self._extract_text(response)
        except errors.APIError as exc:
            logger.error("Gemini chat error: %s", exc)
            raise ValueError(f"AI service error: {exc}") from exc

        updated_history = contents + [{"role": "model", "parts": [{"text": reply_text}]}]
        return reply_text, updated_history

    def generate_preparedness_plan(
        self,
        location: str,
        family_size: int,
        vulnerabilities: list[str],
        phase: str,
        language: str = "English",
        weather_context: str = "",
    ) -> str:
        """
        Generate a personalised monsoon preparedness plan.

        Args:
            location: City/district name.
            family_size: Number of family members.
            vulnerabilities: E.g. ['elderly', 'infant', 'medical equipment'].
            phase: 'pre-monsoon' | 'active-monsoon' | 'post-monsoon'.
            language: Response language.
            weather_context: Live weather summary if available.
        """
        prompt = self._build_plan_prompt(
            location, family_size, vulnerabilities, phase, language, weather_context
        )
        return self._generate(prompt)

    def generate_checklist(
        self,
        location: str,
        housing_type: str,
        family_size: int,
        language: str = "English",
    ) -> str:
        """
        Generate an emergency preparedness checklist.

        Args:
            location: City/district name.
            housing_type: 'apartment' | 'independent-house' | 'rural-home'.
            family_size: Number of family members.
            language: Response language.
        """
        prompt = self._build_checklist_prompt(location, housing_type, family_size, language)
        return self._generate(prompt)

    def generate_travel_advisory(
        self,
        origin: str,
        destination: str,
        travel_date: str,
        transport_mode: str,
        language: str = "English",
    ) -> str:
        """
        Generate a travel safety advisory for a monsoon-season journey.

        Args:
            origin: Starting location.
            destination: End destination.
            travel_date: Date in YYYY-MM-DD format.
            transport_mode: 'car' | 'bike' | 'bus' | 'train' | 'flight'.
            language: Response language.
        """
        prompt = self._build_travel_prompt(
            origin, destination, travel_date, transport_mode, language
        )
        return self._generate(prompt)

    def generate_alerts(
        self,
        location: str,
        phase: str,
        language: str = "English",
        weather_context: str = "",
    ) -> str:
        """
        Generate structured, phase-specific safety alerts.

        Args:
            location: City/district name.
            phase: 'before' | 'during' | 'after'.
            language: Response language.
            weather_context: Live weather summary if available.
        """
        prompt = self._build_alerts_prompt(location, phase, language, weather_context)
        return self._generate(prompt)

    # ── Private prompt builders ───────────────────────────────

    @staticmethod
    def _build_chat_message(message: str, language: str, weather_context: str) -> str:
        parts = [message]
        if weather_context:
            parts.append(f"\n[Current weather context: {weather_context}]")
        parts.append(f"\n[Please respond in: {language}]")
        return "".join(parts)

    @staticmethod
    def _build_plan_prompt(
        location: str,
        family_size: int,
        vulnerabilities: list[str],
        phase: str,
        language: str,
        weather_context: str,
    ) -> str:
        vuln_str = ", ".join(vulnerabilities) if vulnerabilities else "none specified"
        weather_line = f"\nCurrent weather data: {weather_context}" if weather_context else ""
        return f"""Create a comprehensive, personalised monsoon preparedness plan for:
- Location: {location}
- Family size: {family_size} people
- Special vulnerabilities: {vuln_str}
- Monsoon phase: {phase}
{weather_line}

Structure your response with these sections:
1. 🔴 Immediate Actions (next 24 hours)
2. 🏠 Home Preparation
3. 🎒 Emergency Kit — tailored to this family profile
4. 📞 Emergency Contacts & Evacuation Plan
5. 🌊 Specific Risks for {location} and how to mitigate them
6. ✅ Daily Monitoring Checklist

Make the plan specific, practical, and actionable. 
Respond in: {language}"""

    @staticmethod
    def _build_checklist_prompt(
        location: str, housing_type: str, family_size: int, language: str
    ) -> str:
        return f"""Generate a detailed monsoon emergency preparedness checklist for:
- Location: {location}
- Housing type: {housing_type}
- Family size: {family_size} people

Organise checklist into these categories:
📦 Emergency Supplies (72-hour kit)
💧 Water & Food
🏥 First Aid & Medicines
📱 Communication & Documents
🔦 Power & Lighting
🏠 Home Safety & Waterproofing
🚗 Vehicle & Travel Readiness
👨‍👩‍👧 Family Safety Plan

For each item, indicate priority: [CRITICAL] [IMPORTANT] [NICE-TO-HAVE]
Make it specific to a {housing_type} in {location}.
Respond in: {language}"""

    @staticmethod
    def _build_travel_prompt(
        origin: str,
        destination: str,
        travel_date: str,
        transport_mode: str,
        language: str,
    ) -> str:
        return f"""Provide a detailed monsoon travel advisory for:
- Journey: {origin} → {destination}
- Date: {travel_date}
- Mode of transport: {transport_mode}

Include:
⚠️ Risk Assessment (route-specific monsoon hazards)
🛣️ Safer Route Alternatives (if applicable)
📋 Pre-departure Checklist for {transport_mode} travel
🚨 Emergency Protocols if conditions worsen mid-journey
📞 Key helpline numbers (highway patrol, NDRF, state emergency)
⏰ Best & worst times to travel on this date
❌ Go/No-Go recommendation with clear reasoning

Respond in: {language}"""

    @staticmethod
    def _build_alerts_prompt(location: str, phase: str, language: str, weather_context: str) -> str:
        weather_line = f"\nCurrent weather data: {weather_context}" if weather_context else ""
        phase_map = {
            "before": "pre-monsoon (onset approaching in 1-2 weeks)",
            "during": "active monsoon (heavy rainfall currently occurring)",
            "after": "post-monsoon (receding waters, recovery phase)",
        }
        phase_desc = phase_map.get(phase, phase)
        return f"""Generate structured safety alerts for {location} during the {phase_desc} phase.
{weather_line}

Provide alerts in this exact format:
🔴 RED ALERT — [Critical immediate dangers]
🟠 ORANGE ALERT — [High-risk warnings requiring action]
🟡 YELLOW ALERT — [Precautionary advisories]
🟢 SAFE ZONES & RESOURCES — [Where to go, help available]
📞 EMERGENCY NUMBERS — [Relevant contacts for {location}]
💬 COMMUNITY GUIDANCE — [How to help neighbours, community action]

Keep alerts concise, urgent, and actionable.
Respond in: {language}"""

    # ── Private helpers ───────────────────────────────────────

    def _generate(self, prompt: str) -> str:
        """Send a single-turn generation request and return text."""
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=self._config,
            )
            return self._extract_text(response)
        except errors.APIError as exc:
            logger.error("Gemini generation error: %s", exc)
            raise ValueError(f"AI service error: {exc}") from exc

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Safely extract text from a Gemini response object."""
        try:
            return response.text
        except (AttributeError, ValueError) as exc:
            # Response may be blocked by safety filters
            logger.warning("Could not extract text from Gemini response: %s", exc)
            return (
                "I'm unable to generate a response for that request. "
                "Please rephrase your question or contact emergency services if this is urgent."
            )
