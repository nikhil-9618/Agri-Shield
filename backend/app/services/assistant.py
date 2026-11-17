"""Voice-assistant answer engine.

This is deliberately *retrieval*, not free generation: questions are matched to
reviewed advisory content and FAQ entries, and weather questions are answered
from Open-Meteo. When nothing matches, the assistant says so instead of guessing.
"""

from __future__ import annotations

import re
from typing import Any

from .advisory import AdvisoryService
from .weather import WeatherService

LANGUAGE_SCRIPTS = {
    "te": ("\u0c00", "\u0c7f"),
    "hi": ("\u0900", "\u097f"),
    "ta": ("\u0b80", "\u0bff"),
    "kn": ("\u0c80", "\u0cff"),
}

WEATHER_KEYWORDS = [
    "వాతావరణ", "వర్ష", "వాన", "मौसम", "बारिश", "वर्षा", "weather", "rain",
    "forecast", "வானிலை", "மழை", "ಹವಾಮಾನ", "ಮಳೆ", "తేమ", "नमी", "humidity",
]


def detect_language(text: str) -> str:
    """Detect the script of the question; English is the default."""
    for lang, (start, end) in LANGUAGE_SCRIPTS.items():
        if any(start <= ch <= end for ch in text):
            return lang
    return "en"


class AssistantService:
    def __init__(self, advisory: AdvisoryService, weather: WeatherService) -> None:
        self.advisory = advisory
        self.weather = weather

    def _match_intent(self, question: str) -> dict[str, Any] | None:
        best: tuple[int, dict[str, Any]] | None = None
        q = question.lower()
        for intent in self.advisory.faq["intents"]:
            hits = sum(1 for kw in intent["keywords"] if kw.lower() in q)
            if hits and (best is None or hits > best[0]):
                best = (hits, intent)
        return best[1] if best else None

    async def ask(
        self,
        question: str,
        language: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> dict[str, Any]:
        lang = language or detect_language(question)
        q = question.lower()
        sources: list[dict[str, str]] = []
        used_weather = False
        answer: str | None = None

        # 1. Weather questions -------------------------------------------------
        is_weather = any(kw in q for kw in WEATHER_KEYWORDS)
        if is_weather:
            used_weather = True
            if latitude is not None and longitude is not None:
                current = await self.weather.current(latitude, longitude, lang)
                temp = current["current"].get("temperature_c")
                humidity = current["current"].get("humidity")
                rain_t = current["current"].get("rain_probability_tomorrow")
                condition = current["current"].get("condition", "")
                alert_msg = current["alerts"][0]["message"] if current["alerts"] else ""
                answer = (
                    f"{condition}. {temp}°C, "
                    f"{self._label('humidity', lang)} {humidity}%. "
                    + (
                        f"{self._label('rain_prob', lang)}: {rain_t}%. "
                        if rain_t is not None
                        else ""
                    )
                    + alert_msg
                )
                sources.append(
                    {"title": "Open-Meteo forecast", "reference": "https://open-meteo.com/"}
                )
            else:
                answer = self.advisory.t("weather_need_location", lang)

        # 2. Disease questions -------------------------------------------------
        if answer is None:
            disease_key = self.advisory.find_disease_in_text(question, lang)
            if disease_key:
                block = self.advisory.localised(disease_key, lang)
                crop = self.advisory.crop_name(self.advisory.crop_of(disease_key), lang)
                answer = (
                    f"{crop}: {block['name']}. {block['signs']} {block['do_now']} "
                    f"{block['expert']}"
                )
                sources.append(
                    {
                        "title": f"{self.advisory.t('advisory_source', lang)} — {block['name']}",
                        "reference": f"advisory/diseases/{disease_key}.json",
                    }
                )

        # 3. FAQ intents -------------------------------------------------------
        if answer is None:
            intent = self._match_intent(question)
            if intent:
                answer = intent["answer"].get(lang) or intent["answer"]["en"]
                sources.append(
                    {
                        "title": self.advisory.t("faq_source", lang),
                        "reference": f"advisory/assistant_faq.json#{intent['id']}",
                    }
                )

        # 4. Honest fallback ---------------------------------------------------
        if answer is None:
            answer = self.advisory.faq["fallback"].get(lang, self.advisory.faq["fallback"]["en"])

        follow_ups = self.advisory.faq["follow_ups"].get(lang, self.advisory.faq["follow_ups"]["en"])
        return {
            "answer": answer,
            "language": lang,
            "sources": sources,
            "follow_ups": follow_ups,
            "used_weather": used_weather,
            "disclaimer": self.advisory.t("disclaimer", lang),
        }

    @staticmethod
    def _label(key: str, lang: str) -> str:
        from .weather import LABELS

        return LABELS[key].get(lang, LABELS[key]["en"])


def normalise_question(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
