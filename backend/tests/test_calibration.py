"""The API must serve calibrated confidence, not raw softmax.

Farmers see the abstention decision, so the calibration file is part of the
contract: if temperature is not applied, the thresholds are meaningless.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

TMP = Path(tempfile.mkdtemp(prefix="agrishield-cal-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TMP/'test.db'}")
os.environ.setdefault("UPLOAD_DIR", str(TMP / "uploads"))
os.environ.setdefault("GRADCAM_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789")

from app.config import REPO_ROOT  # noqa: E402
from app.services.vision import get_vision_service  # noqa: E402

CALIBRATION = REPO_ROOT / "ml/artifacts/calibration.json"


def test_service_reads_shipped_calibration() -> None:
    if not CALIBRATION.exists():
        import pytest

        pytest.skip("calibration file missing")
    data = json.loads(CALIBRATION.read_text())
    service = get_vision_service()

    assert service.temperature == data["temperature"]
    assert service.min_confidence == data["min_confidence"]
    assert service.healthy_confidence == data["healthy_confidence"]


def test_predictions_are_calibrated_probabilities() -> None:
    service = get_vision_service()
    if not service.available:
        import pytest

        pytest.skip(f"model unavailable: {service.load_error}")

    image = Image.new("RGB", (256, 256), (48, 110, 52))
    result = service.predict(image)
    top3 = result["top3"]

    assert sum(item["confidence"] for item in top3) <= 1.0001
    assert all(0.0 <= item["confidence"] <= 1.0 for item in top3)
    assert top3[0]["confidence"] == max(item["confidence"] for item in top3)
    assert result["temperature"] == service.temperature
    assert result["min_confidence"] == service.min_confidence


def test_backend_scaling_matches_training_module() -> None:
    """The API duplicates apply_temperature to avoid importing `ml` in prod.

    That duplication is only safe while both implementations agree.
    """
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from ml.calibration.calibration import apply_temperature as shared

    from app.services.vision import apply_temperature as backend

    rng = np.random.default_rng(3)
    probs = rng.dirichlet(np.ones(38), size=25).astype(np.float32)
    for temperature in (0.5, 0.875, 2.0):
        expected = shared(probs, temperature)
        actual = np.stack([backend(row, temperature) for row in probs])
        assert np.allclose(actual, expected, atol=1e-6), temperature


def test_temperature_is_applied_to_probabilities() -> None:
    """The service must not return the raw softmax when T != 1."""
    service = get_vision_service()
    if not service.available:
        import pytest

        pytest.skip(f"model unavailable: {service.load_error}")

    raw = np.array([0.9, 0.05, 0.05] + [0.0] * (len(service.classes) - 3), dtype=np.float32)
    from app.services.vision import apply_temperature

    scaled = apply_temperature(raw, service.temperature)
    if service.temperature == 1.0:
        assert np.allclose(scaled, raw)
    else:
        assert not np.allclose(scaled, raw)
    assert int(scaled.argmax()) == 0
