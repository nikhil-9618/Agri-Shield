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


def _contains_keyword(text: str, keyword: str) -> bool:
    """Whole-word match for Latin keywords, substring for Indic scripts.

    Substring matching answered "water-soaked patches" (late blight) with the
    watering FAQ, because ``"water" in question`` is true there.
    """
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    if re.fullmatch(r"[a-z0-9 ]+", keyword):
        # Hyphens count as word characters, so "water" does not match
        # "water-soaked" but still matches "water my plants".
        return (
            re.search(
                rf"(?<![a-z0-9-]){re.escape(keyword)}(?![a-z0-9-])", text
            )
            is not None
        )
    return keyword in text


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
            hits = sum(1 for kw in intent["keywords"] if _contains_keyword(q, kw))
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
        is_weather = any(_contains_keyword(q, kw) for kw in WEATHER_KEYWORDS)
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
        disease_key: str | None = None
        intent: dict[str, Any] | None = None
        if answer is None:
            disease_key = self.advisory.find_disease_in_text(question, lang)
            intent = self._match_intent(question)
            # "Why are my leaves yellow?" is general advice, not a diagnosis,
            # so a matching FAQ wins when no crop is named. A named crop means
            # the farmer is asking about that crop's disease.
            if disease_key and not self.advisory.crops_in_text(question) and intent:
                disease_key = None
        if answer is None and disease_key:
            answer, source = self._advisory_answer(disease_key, lang)
            sources.append(source)

        # 3. FAQ intents -------------------------------------------------------
        if answer is None:
            if intent is None:
                intent = self._match_intent(question)
            if intent:
                answer = intent["answer"].get(lang) or intent["answer"]["en"]
                sources.append(
                    {
                        "title": self.advisory.t("faq_source", lang),
                        "reference": f"advisory/assistant_faq.json#{intent['id']}",
                    }
                )

        # 4. Several reviewed advisories fit the named crop --------------------
        # "Brown spots on tomato" could be early blight, target spot or several
        # others. Listing them with their distinguishing signs is more useful
        # than guessing one, and stays inside reviewed content.
        if answer is None and intent is None:
            candidates = self.advisory.candidate_diseases(question, lang)
            # One reviewed advisory fits the signs: answer it. Several fit:
            # list them with their distinguishing signs rather than guessing.
            if len(candidates) == 1:
                answer, source = self._advisory_answer(candidates[0]["key"], lang)
                sources.append(source)
            elif candidates:
                crop = self.advisory.crop_name(
                    self.advisory.crop_of(candidates[0]["key"]), lang
                )
                listing = " ".join(
                    f"{index}) {item['name']} — {item['signs']}"
                    for index, item in enumerate(candidates, start=1)
                )
                answer = self.advisory.t(
                    "disease_possibilities", lang, crop=crop, list=listing
                )
                for item in candidates:
                    sources.append(
                        self._advisory_source(item["name"], item["key"], lang)
                    )

        # 5. Honest fallback ---------------------------------------------------
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

    # ----------------------------------------------------------- answer parts
    def _advisory_answer(self, key: str, lang: str) -> tuple[str, dict[str, str]]:
        """The reviewed answer text and source entry for one disease advisory."""
        block = self.advisory.localised(key, lang)
        crop = self.advisory.crop_name(self.advisory.crop_of(key), lang)
        text = (
            f"{crop}: {block['name']}. {block['signs']} {block['do_now']} "
            f"{block['expert']}"
        )
        return text, self._advisory_source(block["name"], key, lang)

    def _advisory_source(
        self, name: str, key: str, lang: str
    ) -> dict[str, str]:
        return {
            "title": f"{self.advisory.t('advisory_source', lang)} — {name}",
            "reference": f"advisory/diseases/{key}.json",
        }

    @staticmethod
    def _label(key: str, lang: str) -> str:
        from .weather import LABELS

        return LABELS[key].get(lang, LABELS[key]["en"])


def normalise_question(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
