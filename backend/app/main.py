"""AgriShield FastAPI application."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .api import advisory as advisory_api
from .api import assistant as assistant_api
from .api import auth as auth_api
from .api import detection as detection_api
from .api import user as user_api
from .api import weather as weather_api
from .config import settings
from .db import init_db
from .services.advisory import get_advisory_service
from .services.vision import get_vision_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("agrishield")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small fixed-window limiter (per client IP + path).

    In production behind multiple instances, move this to Redis; the interface
    stays the same.
    """

    def __init__(self, app, limit: int, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/"}:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        key = (client, request.url.path)
        now = time.time()
        with self._lock:
            recent = [t for t in self._hits[key] if now - t < self.window]
            if len(recent) >= self.limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": {
                            "code": "rate_limited",
                            "message": "Too many requests. Please wait a minute and try again.",
                        }
                    },
                    headers={"Retry-After": str(self.window)},
                )
            recent.append(now)
            self._hits[key] = recent
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    vision = get_vision_service()
    if not vision.available:
        logger.warning(
            "Model not loaded: %s. /api/detection/predict will return 503 until "
            "ml/artifacts/agrishield_model.tflite exists.",
            vision.load_error,
        )
    else:
        logger.info("AgriShield model ready: %s", vision.model_version)
    logger.info("Advisory knowledge base: %d diseases", len(get_advisory_service().diseases))
    yield


app = FastAPI(
    title="AgriShield API",
    description="Farmer-first crop disease detection and advisory API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_minute)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "code": "validation_error",
                "message": "Some information is missing or invalid.",
                "errors": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {"code": "server_error", "message": "Something went wrong. Please try again."}
        },
    )


app.include_router(auth_api.router)
app.include_router(user_api.router)
app.include_router(detection_api.router)
app.include_router(weather_api.router)
app.include_router(advisory_api.router)
app.include_router(assistant_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    vision = get_vision_service()
    advisory = get_advisory_service()
    return {
        "status": "ok",
        "model_loaded": vision.available,
        "model_version": vision.model_version if vision.available else None,
        "model_error": None if vision.available else vision.load_error,
        "gradcam_enabled": settings.gradcam_enabled,
        "advisory_languages": ["te", "hi", "en", "ta", "kn"],
        "advisory_diseases": len(advisory.diseases),
        "environment": settings.app_env,
    }


@app.get("/api/meta", tags=["meta"])
def meta(lang: str = "te") -> dict[str, Any]:
    advisory = get_advisory_service()
    language = advisory.normalize_language(lang)
    return {
        "app": "AgriShield",
        "languages": ["te", "hi", "en", "ta", "kn"],
        "default_language": "te",
        "crops": advisory.list_crops(language),
        "diseases": advisory.list_diseases(language),
        "disclaimer": advisory.t("disclaimer", language),
        "model_loaded": get_vision_service().available,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "AgriShield API",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }
