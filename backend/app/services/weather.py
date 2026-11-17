"""Open-Meteo weather integration and crop environmental-risk rules.

Weather facts come only from Open-Meteo. Risks are expressed as *environmental
conditions* (humidity, rain, heat) — never as a confirmed disease.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

import httpx

from ..config import settings
from .advisory import AdvisoryService

WMO_CONDITIONS = {
    0: "clear",
    1: "clear",
    2: "cloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "rain",
    53: "rain",
    55: "rain",
    56: "rain",
    57: "rain",
    61: "rain",
    63: "rain",
    65: "heavy_rain",
    66: "rain",
    67: "rain",
    71: "snow",
    73: "snow",
    75: "snow",
    80: "rain",
    81: "rain",
    82: "heavy_rain",
    95: "storm",
    96: "storm",
    99: "storm",
}

CONDITION_LABELS = {
    "clear": {"te": "నిర్మలంగా", "hi": "साफ", "en": "Clear", "ta": "தெளிவு", "kn": "ಸ್ವಚ್ಛ"},
    "cloudy": {"te": "మేఘావృతం", "hi": "बादल", "en": "Cloudy", "ta": "மேகமூட்டம்", "kn": "ಮೋಡ"},
    "rain": {"te": "వర్షం", "hi": "बारिश", "en": "Rain", "ta": "மழை", "kn": "ಮಳೆ"},
    "heavy_rain": {"te": "భారీ వర్షం", "hi": "भारी बारिश", "en": "Heavy rain", "ta": "கனமழை", "kn": "ಭಾರಿ ಮಳೆ"},
    "storm": {"te": "ఉరుములతో వర్షం", "hi": "आंधी-तूफान", "en": "Thunderstorm", "ta": "இடியுடன் மழை", "kn": "ಗುಡುಗು ಮಳೆ"},
    "fog": {"te": "పొగమంచు", "hi": "कोहरा", "en": "Fog", "ta": "பனிமூட்டம்", "kn": "ಮಂಜು"},
    "snow": {"te": "మంచు", "hi": "बर्फ", "en": "Snow", "ta": "பனி", "kn": "ಹಿಮ"},
}

LABELS = {
    "humidity": {"te": "తేమ", "hi": "नमी", "en": "Humidity", "ta": "ஈரப்பதம்", "kn": "ತೇವ"},
    "temperature": {"te": "ఉష్ణోగ్రత", "hi": "तापमान", "en": "Temperature", "ta": "வெப்பநிலை", "kn": "ಉಷ್ಣಾಂಶ"},
    "rain_prob": {"te": "వర్ష సంభావ్యత", "hi": "बारिश की संभावना", "en": "Rain chance", "ta": "மழை வாய்ப்பு", "kn": "ಮಳೆ ಸಾಧ್ಯತೆ"},
    "wind": {"te": "గాలి వేగం", "hi": "हवा की गति", "en": "Wind speed", "ta": "காற்று வேகம்", "kn": "ಗಾಳಿ ವೇಗ"},
}

# Crops in the app and the humid/wet conditions that favour their main diseases.
SENSITIVE_CROPS = {"tomato", "potato", "pepper", "corn", "apple", "grape"}


class WeatherService:
    def __init__(self, advisory: AdvisoryService) -> None:
        self.advisory = advisory
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def _get(self, lat: float, lon: float) -> dict[str, Any]:
        key = f"{round(lat, 3)},{round(lon, 3)}"
        cached = self._cache.get(key)
        if cached and time.time() - cached[0] < settings.weather_cache_seconds:
            return cached[1]
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "hourly": "precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 7,
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(settings.open_meteo_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        self._cache[key] = (time.time(), data)
        return data

    # ------------------------------------------------------------------ helpers
    def _condition(self, code: int | None, lang: str) -> str:
        name = WMO_CONDITIONS.get(int(code or 0), "cloudy")
        return CONDITION_LABELS[name].get(lang, CONDITION_LABELS[name]["en"])

    def _rule_alert(self, rule: str, lang: str) -> dict[str, Any]:
        rule_data = self.advisory.weather_rules[rule]
        return {
            "level": rule_data["level"],
            "icon": rule_data["icon"],
            "title": rule_data["title"].get(lang, rule_data["title"]["en"]),
            "message": rule_data["message"].get(lang, rule_data["message"]["en"]),
        }

    def _active_rules(self, current: dict, daily: dict) -> list[str]:
        rules: list[str] = []
        humidity = float(current.get("relative_humidity_2m") or 0)
        temp = float(current.get("temperature_2m") or 0)
        wind = float(current.get("wind_speed_10m") or 0)
        rain_probs = [p for p in (daily.get("precipitation_probability_max") or []) if p is not None]
        rain_tomorrow = rain_probs[1] if len(rain_probs) > 1 else (rain_probs[0] if rain_probs else 0)
        if rain_tomorrow and rain_tomorrow >= 60:
            rules.append("rain_soon")
        if humidity >= 85:
            rules.append("high_humidity")
        if temp >= 38:
            rules.append("heat_stress")
        if wind >= 35:
            rules.append("windy")
        if not rules and rain_probs and max(rain_probs) < 20 and humidity < 60:
            rules.append("dry_spell")
        return rules or ["good_weather"]

    # -------------------------------------------------------------------- public
    async def current(self, lat: float, lon: float, lang: str) -> dict[str, Any]:
        data = await self._get(lat, lon)
        current = data.get("current", {})
        daily = data.get("daily", {})
        rules = self._active_rules(current, daily)
        alerts = [self._rule_alert(r, lang) for r in rules]
        return {
            "location": {
                "latitude": lat,
                "longitude": lon,
                "timezone": data.get("timezone", "auto"),
                "elevation": data.get("elevation"),
            },
            "current": {
                "temperature_c": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "rainfall_mm": current.get("precipitation", 0.0),
                "wind_kmh": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code"),
                "condition": self._condition(current.get("weather_code"), lang),
                "rain_probability_tomorrow": (
                    (daily.get("precipitation_probability_max") or [None, None])[1]
                    if daily.get("precipitation_probability_max")
                    else None
                ),
            },
            "alerts": alerts,
            "advice": [a["message"] for a in alerts],
            "fetched_at": dt.datetime.now(dt.timezone.utc),
        }

    async def forecast(self, lat: float, lon: float, lang: str) -> dict[str, Any]:
        data = await self._get(lat, lon)
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        days = []
        for i, day in enumerate(dates[:7]):
            days.append(
                {
                    "date": day,
                    "temp_min_c": (daily.get("temperature_2m_min") or [None] * 7)[i],
                    "temp_max_c": (daily.get("temperature_2m_max") or [None] * 7)[i],
                    "rain_probability": (daily.get("precipitation_probability_max") or [None] * 7)[i],
                    "rain_mm": (daily.get("precipitation_sum") or [None] * 7)[i],
                    "condition": self._condition(
                        (daily.get("weather_code") or [None] * 7)[i], lang
                    ),
                }
            )
        rules = self._active_rules(data.get("current", {}), daily)
        alerts = [self._rule_alert(r, lang) for r in rules]
        return {
            "location": {"latitude": lat, "longitude": lon, "timezone": data.get("timezone")},
            "days": days,
            "alerts": alerts,
            "advice": [a["message"] for a in alerts],
        }

    async def risk(self, lat: float, lon: float, lang: str, crop: str | None = None) -> dict[str, Any]:
        data = await self._get(lat, lon)
        current = data.get("current", {})
        daily = data.get("daily", {})
        rules = self._active_rules(current, daily)
        primary = rules[0]
        humidity = float(current.get("relative_humidity_2m") or 0)
        temp = float(current.get("temperature_2m") or 0)
        rain_prob = (daily.get("precipitation_probability_max") or [None, None])
        tomorrow = rain_prob[1] if len(rain_prob) > 1 else None

        crops = [crop] if crop else [c for c in self.advisory.crops if c in SENSITIVE_CROPS]
        risks = []
        for c in crops:
            if c not in self.advisory.crops:
                continue
            wet_disease_risk = humidity >= 80 or (tomorrow or 0) >= 60
            if primary == "heat_stress":
                level = "red"
            elif primary == "good_weather" and not wet_disease_risk:
                level = "green"
            elif wet_disease_risk and humidity >= 88:
                level = "red"
            else:
                level = "yellow"
            rule_data = self.advisory.weather_rules[primary]
            reasons = [
                f"{LABELS['humidity'].get(lang, 'Humidity')}: {humidity:.0f}%",
                f"{LABELS['temperature'].get(lang, 'Temperature')}: {temp:.1f}°C",
            ]
            if tomorrow is not None:
                reasons.append(
                    f"{LABELS['rain_prob'].get(lang, 'Rain chance')}: {tomorrow}%"
                )
            risks.append(
                {
                    "crop": c,
                    "crop_name": self.advisory.crop_name(c, lang),
                    "level": level,
                    "title": f"{self.advisory.crop_name(c, lang)} — "
                    f"{rule_data['title'].get(lang, rule_data['title']['en'])}",
                    "message": rule_data["message"].get(lang, rule_data["message"]["en"]),
                    "reasons": reasons,
                }
            )
        return {
            "location": {"latitude": lat, "longitude": lon, "timezone": data.get("timezone")},
            "risks": risks,
            "disclaimer": self.advisory.t("disclaimer", lang),
        }
