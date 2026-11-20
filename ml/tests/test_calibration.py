"""Calibration invariants.

Temperature scaling must never change a prediction, and the shipped
calibration.json must stay consistent with the model and the backend. These
tests fail if a refit silently changes accuracy, if the file is nonsense, or if
the API stops applying the same temperature.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CALIBRATION = ROOT / "ml/artifacts/calibration.json"
MOBILE_CALIBRATION = ROOT / "mobile/assets/model/calibration.json"
LABELS = ROOT / "mobile/assets/model/class_names.json"


def test_temperature_preserves_predictions() -> None:
    from ml.calibration.calibration import apply_temperature

    rng = np.random.default_rng(7)
    probs = rng.dirichlet(np.ones(38), size=200)
    scaled = apply_temperature(probs, 0.875)

    assert np.array_equal(probs.argmax(axis=1), scaled.argmax(axis=1))
    assert np.allclose(scaled.sum(axis=1), 1.0, atol=1e-5)
    assert np.all(scaled >= 0.0)


def test_temperature_one_is_identity() -> None:
    from ml.calibration.calibration import apply_temperature

    probs = np.array([0.6, 0.3, 0.1], dtype=np.float32)
    assert np.allclose(apply_temperature(probs, 1.0), probs)


def test_sharpening_and_softening_move_the_right_way() -> None:
    from ml.calibration.calibration import apply_temperature

    probs = np.array([0.6, 0.3, 0.1], dtype=np.float32)
    assert apply_temperature(probs, 0.5).max() > probs.max()
    assert apply_temperature(probs, 2.0).max() < probs.max()


def test_invalid_temperature_is_rejected() -> None:
    from ml.calibration.calibration import apply_temperature

    with pytest.raises(ValueError):
        apply_temperature(np.array([0.5, 0.5]), 0)


@pytest.mark.skipif(not CALIBRATION.exists(), reason="calibration file missing")
def test_calibration_file_is_consistent() -> None:
    data = json.loads(CALIBRATION.read_text())
    labels = json.loads(LABELS.read_text())
    n_classes = len(labels)

    assert 0.2 <= data["temperature"] <= 5.0
    assert data["class_count"] == n_classes
    assert 0.0 < data["min_confidence"] < 1.0
    assert data["min_confidence"] <= data["healthy_confidence"] < 1.0

    # Calibration must not have moved accuracy, and should not have made
    # probabilities worse than raw softmax on held-out data.
    val = data["validation"]
    assert val["uncalibrated"]["accuracy"] == val["calibrated"]["accuracy"]
    assert data["test"]["uncalibrated"]["accuracy"] == data["test"]["calibrated"]["accuracy"]
    assert data["test"]["calibrated"]["ece"] <= data["test"]["uncalibrated"]["ece"] + 1e-9

    # The reported operating point has to match the threshold it ships with.
    assert abs(val["calibrated"]["coverage_at_threshold"] - data["abstention"]["measured_coverage"]) < 0.01


@pytest.mark.skipif(
    not (CALIBRATION.exists() and MOBILE_CALIBRATION.exists()),
    reason="calibration files missing",
)
def test_mobile_bundle_carries_the_same_calibration() -> None:
    repo = json.loads(CALIBRATION.read_text())
    mobile = json.loads(MOBILE_CALIBRATION.read_text())
    for key in ("temperature", "min_confidence", "healthy_confidence"):
        assert mobile[key] == repo[key], key


# The backend-vs-shared-module parity check lives in
# backend/tests/test_calibration.py, where the API dependencies are installed.
