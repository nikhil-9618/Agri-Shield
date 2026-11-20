"""Regression tests for the preprocessing pipeline.

v1.3.0 scored 3.7% top-1 because the app and this service scaled pixels to
[-1, 1] before feeding a model that already does that internally. These tests
fail if anyone reintroduces it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

TMP = Path(tempfile.mkdtemp(prefix="agrishield-pre-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TMP/'test.db'}")
os.environ.setdefault("UPLOAD_DIR", str(TMP / "uploads"))
os.environ.setdefault("GRADCAM_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789")

from app.services.vision import get_vision_service  # noqa: E402


def _solid(value: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (320, 240), value)


def test_preprocess_keeps_raw_pixel_range() -> None:
    service = get_vision_service()
    batch = service._preprocess(_solid((200, 40, 60)))

    assert batch.dtype == np.float32
    assert batch.shape == (1, service.input_size, service.input_size, 3)
    # Raw 0-255 domain: the graph applies preprocess_input itself.
    assert float(batch.min()) >= 0.0
    assert float(batch.max()) <= 255.0
    assert abs(float(batch.mean()) - 100.0) < 3.0


def test_predictions_are_not_constant_across_images() -> None:
    service = get_vision_service()
    if not service.available:
        import pytest

        pytest.skip(f"model unavailable: {service.load_error}")

    leaf = Image.new("RGB", (320, 320), (34, 96, 38))
    draw = ImageDraw.Draw(leaf)
    draw.ellipse((40, 70, 280, 250), fill=(72, 142, 58))
    draw.line((160, 70, 160, 250), fill=(120, 180, 80), width=6)

    a = service.predict(leaf)
    b = service.predict(_solid((240, 240, 235)))

    # Same photo twice must be identical; different photos must not collapse.
    again = service.predict(leaf)
    assert a["prediction"]["key"] == again["prediction"]["key"]
    va = np.array([p["confidence"] for p in a["top3"]])
    vb = np.array([p["confidence"] for p in b["top3"]])
    assert np.abs(va - vb).max() > 1e-3
