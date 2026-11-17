"""Crop/disease advisory content, localised."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ..services.advisory import get_advisory_service

router = APIRouter(prefix="/api/advisory", tags=["advisory"])


@router.get("/crops")
def crops(lang: str = Query(default="te", max_length=5)) -> dict[str, Any]:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang)
    return {"language": language, "crops": advisory.list_crops(language)}


@router.get("")
def catalogue(
    crop: str | None = Query(default=None, max_length=30),
    lang: str = Query(default="te", max_length=5),
) -> dict[str, Any]:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang)
    return {"language": language, "diseases": advisory.list_diseases(language, crop)}


@router.get("/{disease}")
def disease(
    disease: str,
    lang: str = Query(default="te", max_length=5),
) -> dict[str, Any]:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang)
    if disease not in advisory.diseases:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "unknown_disease", "message": "No advisory for this disease key."},
        )
    item = advisory.diseases[disease]
    return {
        "key": disease,
        "crop": item["crop"],
        "crop_name": advisory.crop_name(item["crop"], language),
        "severity": item.get("severity"),
        "is_healthy": item.get("is_healthy", False),
        "icon": item.get("icon"),
        "language": language,
        "advisory": advisory.localised(disease, language),
        "disclaimer": advisory.t("disclaimer", language),
        "available_languages": sorted(item.get("l", {}).keys()),
    }
