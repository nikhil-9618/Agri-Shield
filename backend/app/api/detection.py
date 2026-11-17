"""Camera-image disease detection, history and stored images."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Detection, User, get_db
from ..schemas import DetectionOut, HistoryItem, HistoryOut, Top3Item
from ..security import get_current_user
from ..services.advisory import get_advisory_service
from ..services.vision import InvalidImageError, get_vision_service, read_and_validate_image

router = APIRouter(prefix="/api/detection", tags=["detection"])


def _top3_payload(top3: list[dict], advisory, lang: str) -> list[Top3Item]:
    return [
        Top3Item(
            key=item["key"],
            crop=item["crop"],
            disease=item["disease"],
            confidence=round(item["confidence"], 4),
            crop_name=advisory.crop_name(item["crop"], lang),
            disease_name=advisory.disease_name(item["key"], lang),
            is_healthy=item["is_healthy"],
        )
        for item in top3
    ]


def _build_response(row: Detection, lang: str, gradcam_b64: str | None = None) -> DetectionOut:
    advisory = get_advisory_service()
    block = advisory.localised(row.disease_key, lang)
    stored_top3 = row.top3 or []
    if row.status == "unclear":
        message = advisory.t("unclear", lang)
    elif advisory.is_healthy(row.disease_key):
        message = advisory.t("healthy", lang)
    else:
        message = f"{block['name']}. {block['signs']}"
    return DetectionOut(
        id=row.id,
        created_at=row.created_at,
        status=row.status,  # type: ignore[arg-type]
        level=row.level,  # type: ignore[arg-type]
        language=lang,
        crop_key=row.crop_key,
        crop_name=advisory.crop_name(row.crop_key, lang),
        disease_key=row.disease_key,
        disease_name=block["name"] or advisory.disease_name(row.disease_key, lang),
        confidence=round(row.confidence, 4),
        top3=[Top3Item(**item) for item in stored_top3],
        advisory=block,  # type: ignore[arg-type]
        gradcam_base64=gradcam_b64,
        message=message,
        disclaimer=advisory.t("disclaimer", lang),
        model_version=row.model_version,
        image_url=f"/api/detection/{row.id}/image",
    )


@router.post("/predict", response_model=DetectionOut)
async def predict(
    file: UploadFile = File(...),
    lang: str | None = Query(default=None, max_length=5),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DetectionOut:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang or user.language)

    raw = await file.read()
    try:
        image, normalised = read_and_validate_image(raw)
    except InvalidImageError as exc:
        reason = str(exc)
        message = (
            advisory.t("image_too_large", language)
            if reason == "too_large"
            else advisory.t("invalid_image", language)
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_image", "message": message},
        ) from exc

    vision = get_vision_service()
    if not vision.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "model_unavailable",
                "message": advisory.t("model_unavailable", language),
            },
        )
    try:
        result = vision.predict(image)
    except Exception as exc:  # pragma: no cover - runtime model failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "model_unavailable",
                "message": advisory.t("model_unavailable", language),
            },
        ) from exc

    top3 = result["top3"]
    prediction = result["prediction"]
    confidence = float(prediction["confidence"])
    disease_key = prediction["key"]
    crop_key = prediction["crop"]
    healthy = bool(prediction["is_healthy"])

    if confidence < settings.min_confidence:
        level, diagnosis_status = "yellow", "unclear"
    elif healthy and confidence >= settings.healthy_confidence:
        level, diagnosis_status = "green", "diagnosed"
    else:
        level, diagnosis_status = advisory.severity(disease_key), "diagnosed"

    # Persist a stripped, resized copy of the image (EXIF/GPS removed).
    user_dir = settings.upload_path / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    image_name = f"{uuid.uuid4().hex}.jpg"
    (user_dir / image_name).write_bytes(normalised)

    gradcam_b64: str | None = None
    gradcam_path: str | None = None
    if diagnosis_status == "diagnosed":
        gradcam_b64 = vision.gradcam(normalised, int(result.get("pred_index", 0)))
        if gradcam_b64:
            gc_name = f"gc_{image_name}"
            (user_dir / gc_name).write_bytes(base64.b64decode(gradcam_b64))
            gradcam_path = str(Path(str(user.id)) / gc_name)

    row = Detection(
        user_id=user.id,
        crop_key=crop_key,
        disease_key=disease_key,
        confidence=confidence,
        level=level,
        status=diagnosis_status,
        language=language,
        top3=[item.model_dump() for item in _top3_payload(top3, advisory, language)],
        advisory_snapshot=advisory.localised(disease_key, language),
        image_path=str(Path(str(user.id)) / image_name),
        gradcam_path=gradcam_path,
        model_version=result.get("model_version", "unknown"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _build_response(row, language, gradcam_b64)


@router.get("/history", response_model=HistoryOut)
def history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    lang: str | None = Query(default=None, max_length=5),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryOut:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang or user.language)
    query = db.query(Detection).filter(Detection.user_id == user.id).order_by(
        Detection.created_at.desc()
    )
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    items = [
        HistoryItem(
            id=row.id,
            created_at=row.created_at,
            crop_key=row.crop_key,
            crop_name=advisory.crop_name(row.crop_key, language),
            disease_key=row.disease_key,
            disease_name=advisory.localised(row.disease_key, language)["name"],
            confidence=round(row.confidence, 4),
            level=row.level,
            status=row.status,
            image_url=f"/api/detection/{row.id}/image",
        )
        for row in rows
    ]
    return HistoryOut(total=total, items=items)


@router.get("/{detection_id}", response_model=DetectionOut)
def get_detection(
    detection_id: int,
    lang: str | None = Query(default=None, max_length=5),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DetectionOut:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang or user.language)
    row = (
        db.query(Detection)
        .filter(Detection.id == detection_id, Detection.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Diagnosis not found."},
        )
    gradcam_b64 = None
    if row.gradcam_path:
        gc_file = settings.upload_path / row.gradcam_path
        if gc_file.exists():
            gradcam_b64 = base64.b64encode(gc_file.read_bytes()).decode("ascii")
    return _build_response(row, language, gradcam_b64)


@router.get("/{detection_id}/image")
def get_image(
    detection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    row = (
        db.query(Detection)
        .filter(Detection.id == detection_id, Detection.user_id == user.id)
        .first()
    )
    if row is None or not row.image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Image not found."},
        )
    path = (settings.upload_path / row.image_path).resolve()
    if not str(path).startswith(str(settings.upload_path.resolve())) or not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Image not found."},
        )
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
