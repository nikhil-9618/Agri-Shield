"""Pydantic request/response models with strict validation."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Language = Literal["te", "hi", "en", "ta", "kn"]


class RegisterIn(BaseModel):
    phone: str = Field(pattern=r"^[0-9]{10,15}$", description="Mobile number, digits only")
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=72)
    language: Language = "te"
    village: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)

    @field_validator("name", "village", "state")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            return None
        return v


class LoginIn(BaseModel):
    phone: str = Field(pattern=r"^[0-9]{10,15}$")
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone: str
    name: str
    language: str
    village: str | None = None
    state: str | None = None
    created_at: dt.datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    language: Language | None = None
    village: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=6, max_length=72)


class Top3Item(BaseModel):
    key: str
    crop: str
    disease: str
    confidence: float
    crop_name: str
    disease_name: str
    is_healthy: bool


class AdvisoryBlock(BaseModel):
    name: str
    signs: str
    do_now: str
    avoid: str
    prevention: str
    expert: str


class DetectionOut(BaseModel):
    id: int
    created_at: dt.datetime
    status: Literal["diagnosed", "unclear"]
    level: Literal["green", "yellow", "red"]
    language: str
    crop_key: str
    crop_name: str
    disease_key: str
    disease_name: str
    confidence: float
    top3: list[Top3Item]
    advisory: AdvisoryBlock
    gradcam_base64: str | None = None
    message: str
    disclaimer: str
    model_version: str
    image_url: str | None = None


class HistoryItem(BaseModel):
    id: int
    created_at: dt.datetime
    crop_key: str
    crop_name: str
    disease_key: str
    disease_name: str
    confidence: float
    level: str
    status: str
    image_url: str | None = None


class HistoryOut(BaseModel):
    total: int
    items: list[HistoryItem]


class WeatherAlert(BaseModel):
    level: Literal["green", "yellow", "red"]
    icon: str
    title: str
    message: str


class WeatherCurrentOut(BaseModel):
    location: dict[str, Any]
    current: dict[str, Any]
    alerts: list[WeatherAlert]
    advice: list[str]
    fetched_at: dt.datetime
    source: str = "Open-Meteo"


class ForecastDay(BaseModel):
    date: str
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    rain_probability: int | None = None
    rain_mm: float | None = None
    condition: str


class WeatherForecastOut(BaseModel):
    location: dict[str, Any]
    days: list[ForecastDay]
    alerts: list[WeatherAlert]
    advice: list[str]
    source: str = "Open-Meteo"


class CropRisk(BaseModel):
    crop: str
    crop_name: str
    level: Literal["green", "yellow", "red"]
    title: str
    message: str
    reasons: list[str]


class WeatherRiskOut(BaseModel):
    location: dict[str, Any]
    risks: list[CropRisk]
    disclaimer: str
    source: str = "Open-Meteo"


class AssistantIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    language: Language | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AssistantSource(BaseModel):
    title: str
    reference: str


class AssistantOut(BaseModel):
    answer: str
    language: str
    sources: list[AssistantSource]
    follow_ups: list[str]
    used_weather: bool
    disclaimer: str
