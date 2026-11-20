"""Single-image inference used by tests and by the API's contract checks.

The app and the FastAPI service each have their own inference code for good
reasons (Dart on the phone, LiteRT in the container), but they must behave
identically. This module is the reference implementation: raw 0-255 float32
pixels, temperature-scaled confidence, and an explicit ``unclear`` status
instead of a forced answer.

    from ml.inference.predictor import Predictor
    predictor = Predictor()
    result = predictor.predict_image("leaf.jpg")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ml.calibration.calibration import apply_temperature, load_calibration

DEFAULT_MODEL = "mobile/assets/model/agrishield_model.tflite"
DEFAULT_LABELS = "mobile/assets/model/class_names.json"
DEFAULT_CALIBRATION = "ml/artifacts/calibration.json"


class Predictor:
    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL,
        labels_path: str | Path = DEFAULT_LABELS,
        calibration_path: str | Path = DEFAULT_CALIBRATION,
    ) -> None:
        from ai_edge_litert.interpreter import Interpreter

        self.model_path = Path(model_path)
        self.labels = json.loads(Path(labels_path).read_text())
        calibration = load_calibration(calibration_path)
        self.temperature = float(calibration["temperature"])
        self.min_confidence = float(calibration["min_confidence"])
        self.healthy_confidence = float(calibration["healthy_confidence"])

        self.interpreter = Interpreter(model_path=str(self.model_path))
        self.interpreter.allocate_tensors()
        self._input = self.interpreter.get_input_details()[0]
        self._output = self.interpreter.get_output_details()[0]
        self.input_size = int(self._input["shape"][1])
        self._by_index = {c["index"]: c for c in self.labels}

    def predict_array(self, arr: np.ndarray) -> dict[str, Any]:
        """Predict from a 0-255 float32 (H, W, 3) RGB array."""
        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError(f"expected (H, W, 3) RGB array, got {arr.shape}")
        batch = arr.reshape(1, *arr.shape).astype(np.float32)
        if arr.shape[0] != self.input_size or arr.shape[1] != self.input_size:
            raise ValueError(
                f"expected {self.input_size}x{self.input_size}, got {arr.shape[:2]}"
            )
        self.interpreter.set_tensor(self._input["index"], batch)
        self.interpreter.invoke()
        raw = np.asarray(self.interpreter.get_tensor(self._output["index"]))[0]
        probs = apply_temperature(raw, self.temperature)

        order = np.argsort(probs)[::-1]
        top = order[0]
        confidence = float(probs[top])
        meta = self._by_index[int(top)]
        status = "unclear"
        if confidence >= self.min_confidence:
            status = "diagnosed"
        elif meta.get("is_healthy") and confidence >= self.healthy_confidence:
            status = "diagnosed"

        return {
            "status": status,
            "level": "yellow"
            if status == "unclear"
            else ("green" if meta.get("is_healthy") else "red"),
            "disease_key": meta["key"],
            "crop": meta["crop"],
            "disease": meta["disease"],
            "is_healthy": bool(meta.get("is_healthy")),
            "confidence": round(confidence, 4),
            "temperature": self.temperature,
            "min_confidence": self.min_confidence,
            "top3": [
                {
                    "key": self._by_index[int(i)]["key"],
                    "confidence": round(float(probs[i]), 4),
                }
                for i in order[:3]
            ],
        }

    def predict_image(self, path: str | Path) -> dict[str, Any]:
        with Image.open(path) as im:
            arr = np.asarray(
                im.convert("RGB").resize(
                    (self.input_size, self.input_size), Image.BILINEAR
                ),
                dtype=np.float32,
            )
        return self.predict_array(arr)
