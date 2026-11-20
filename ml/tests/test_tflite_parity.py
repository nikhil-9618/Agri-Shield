"""Keras vs TFLite parity.

Both runtimes must see the same pixels and agree on the predicted class. This
catches export drift and the double-preprocessing bug that made every photo
report "common rust".

    python -m pytest ml/tests -q
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

ROOT = Path(__file__).resolve().parents[2]
# Compare the two artifacts that are actually shipped together. Pointing this at
# an older run directory silently compares two different models.
KERAS = ROOT / "ml/artifacts/agrishield_model.keras"
TFLITE = ROOT / "mobile/assets/model/agrishield_model.tflite"
DATASET = Path(os.environ.get("AGRISHIELD_TEST_DIR", "/tmp/agrishield_v3/test"))


def _sample_images(limit: int = 200):
    files = sorted(DATASET.rglob("*.jpg"))[:limit] if DATASET.exists() else []
    if not files:
        pytest.skip(f"no test images under {DATASET}")
    return files


@pytest.mark.skipif(not TFLITE.exists(), reason="tflite model missing")
def test_tflite_reacts_to_input() -> None:
    from ai_edge_litert.interpreter import Interpreter

    it = Interpreter(model_path=str(TFLITE))
    it.allocate_tensors()
    inp = it.get_input_details()[0]
    out = it.get_output_details()[0]
    size = int(inp["shape"][1])

    def run(image: np.ndarray) -> np.ndarray:
        it.set_tensor(inp["index"], image.reshape(1, size, size, 3).astype(np.float32))
        it.invoke()
        return it.get_tensor(out["index"])[0]

    rng = np.random.default_rng(0)
    noise = rng.integers(0, 256, (size, size, 3)).astype(np.float32)
    black = np.zeros((size, size, 3), dtype=np.float32)
    probs_noise, probs_black = run(noise), run(black)

    assert np.abs(probs_noise - probs_black).max() > 1e-3, "model ignores its input"


@pytest.mark.skipif(not (KERAS.exists() and TFLITE.exists()), reason="artifacts missing")
def test_keras_tflite_agree() -> None:
    import tensorflow as tf
    from ai_edge_litert.interpreter import Interpreter
    from PIL import Image

    model = tf.keras.models.load_model(str(KERAS), compile=False)
    it = Interpreter(model_path=str(TFLITE))
    it.allocate_tensors()
    inp = it.get_input_details()[0]
    out = it.get_output_details()[0]
    size = int(inp["shape"][1])

    agree = 0
    files = _sample_images()
    for path in files:
        raw = np.asarray(
            Image.open(path).convert("RGB").resize((size, size), Image.BILINEAR),
            dtype=np.float32,
        )
        keras_pred = int(np.argmax(model.predict(raw[None, ...], verbose=0)[0]))
        it.set_tensor(inp["index"], raw.reshape(1, size, size, 3))
        it.invoke()
        tflite_pred = int(np.argmax(it.get_tensor(out["index"])[0]))
        agree += keras_pred == tflite_pred

    # 24 images was too few to test a 0.99 threshold: one near-tie is 4%.
    rate = agree / len(files)
    print(f"keras/tflite agreement: {rate:.3f} on {len(files)} images")
    assert rate >= 0.99, f"agreement {rate:.3f} below 0.99"


@pytest.mark.skipif(not TFLITE.exists(), reason="tflite model missing")
def test_class_index_matches_labels() -> None:
    from ai_edge_litert.interpreter import Interpreter

    it = Interpreter(model_path=str(TFLITE))
    it.allocate_tensors()
    n_outputs = int(it.get_output_details()[0]["shape"][-1])
    labels = json.loads((ROOT / "mobile/assets/model/class_names.json").read_text())
    assert len(labels) == n_outputs
    assert [c["index"] for c in labels] == list(range(n_outputs))
