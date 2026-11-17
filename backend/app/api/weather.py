"""Open-Meteo weather, forecast and crop environmental risk."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from ..schemas import WeatherCurrentOut, WeatherForecastOut, WeatherRiskOut
from ..services.advisory import get_advisory_service
from ..services.weather import WeatherService

router = APIRouter(prefix="/api/weather", tags=["weather"])

_service = WeatherService(get_advisory_service())


def get_weather_service() -> WeatherService:
    return _service


async def _guard(coro, lang: str = "en"):
    try:
        return await coro
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "weather_unavailable",
                "message": get_advisory_service().weather_rules["unavailable"]["message"].get(
                    lang, "Weather service is not reachable right now. Please try again later."
                ),
            },
        ) from exc


@router.get("/current", response_model=WeatherCurrentOut)
async def current(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lang: str = Query(default="te", max_length=5),
) -> WeatherCurrentOut:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang)
    data = await _guard(_service.current(lat, lon, language), language)
    return WeatherCurrentOut(**data)


@router.get("/forecast", response_model=WeatherForecastOut)
async def forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lang: str = Query(default="te", max_length=5),
) -> WeatherForecastOut:
    language = get_advisory_service().normalize_language(lang)
    data = await _guard(_service.forecast(lat, lon, language), language)
    return WeatherForecastOut(**data)


@router.get("/risk", response_model=WeatherRiskOut)
async def risk(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lang: str = Query(default="te", max_length=5),
    crop: str | None = Query(default=None, max_length=30),
) -> WeatherRiskOut:
    language = get_advisory_service().normalize_language(lang)
    data = await _guard(_service.risk(lat, lon, language, crop), language)
    return WeatherRiskOut(**data)
