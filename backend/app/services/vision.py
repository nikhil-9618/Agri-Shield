"""Crop-disease inference.

Primary path is the exported TensorFlow Lite model (fast, small). Grad-CAM
explanations need the Keras model and TensorFlow; when either is missing the API
still returns real predictions but with ``gradcam_base64 = None`` — it never
invents an explanation.

Nothing here decides a result by itself: predictions come from the trained model.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from ..config import settings

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}
MAX_DIMENSION = 1600
MIN_DIMENSION = 96


class InvalidImageError(ValueError):
    pass


def read_and_validate_image(raw: bytes) -> tuple[Image.Image, bytes]:
    """Validate an upload and return (RGB image, normalised JPEG bytes).

    Re-encoding strips EXIF/GPS metadata so farmer location never leaks through
    the photo, and caps the stored size.
    """
    if len(raw) == 0:
        raise InvalidImageError("empty file")
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidImageError("too_large")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("not_an_image") from exc
    if img.format not in ALLOWED_FORMATS:
        raise InvalidImageError("unsupported_format")
    if min(img.size) < MIN_DIMENSION:
        raise InvalidImageError("too_small")
    img = img.convert("RGB")
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return img, out.getvalue()


class VisionService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.interpreter = None
        self.input_detail: dict[str, Any] | None = None
        self.output_detail: dict[str, Any] | None = None
        self.classes: list[dict[str, Any]] = []
        self.input_size = 128
        self.model_version = "unavailable"
        self.load_error: str | None = None
        self._keras_model = None
        self._keras_error: str | None = None
        self._load()

    # -------------------------------------------------------------- loading
    @staticmethod
    def _make_interpreter(model_path: str, num_threads: int = 4):
        """Create a TFLite interpreter with the smallest available runtime.

        Production images (Render) install `ai-edge-litert` instead of the whole
        of TensorFlow, which keeps the container inside a 512 MB instance. Both
        runtimes execute the same .tflite file; TensorFlow is only needed for
        Grad-CAM, which is disabled there (`GRADCAM_ENABLED=false`).
        """
        try:
            from ai_edge_litert.interpreter import Interpreter  # type: ignore

            try:
                return Interpreter(model_path=model_path, num_threads=num_threads)
            except TypeError:
                # LiteRT 2.x takes only model_path; threads are set separately.
                interpreter = Interpreter(model_path=model_path)
                setter = getattr(interpreter, "set_num_threads", None)
                if setter is not None:
                    try:
                        setter(num_threads)
                    except Exception:  # pragma: no cover - optional tuning
                        pass
                return interpreter
        except ImportError:
            import tensorflow as tf

            return tf.lite.Interpreter(model_path=model_path, num_threads=num_threads)

    def _load(self) -> None:
        try:
            self.classes = json.loads(settings.class_names_file.read_text("utf-8"))
        except Exception as exc:  # pragma: no cover - missing artifact
            self.load_error = f"class names: {exc}"
            logger.warning("Class names unavailable: %s", exc)
            return

        model_file = settings.model_file
        if not model_file.exists():
            self.load_error = "tflite model missing"
            logger.warning("TFLite model missing at %s", model_file)
            return
        try:
            self.interpreter = self._make_interpreter(str(model_file), num_threads=4)
            self.interpreter.allocate_tensors()
            self.input_detail = self.interpreter.get_input_details()[0]
            self.output_detail = self.interpreter.get_output_details()[0]
            self.input_size = int(self.input_detail["shape"][1])
            digest = hashlib.sha256(model_file.read_bytes()).hexdigest()[:8]
            report = settings.resolve("ml/artifacts/training_report.json")
            trained = ""
            if report.exists():
                meta = json.loads(report.read_text("utf-8"))
                trained = meta.get("timestamp_utc", "")[:10]
            self.model_version = f"mobilenetv2-{self.input_size}-{digest}" + (
                f"-{trained}" if trained else ""
            )
            logger.info("Loaded TFLite model %s", self.model_version)
        except Exception as exc:
            self.load_error = f"tflite: {exc}"
            logger.exception("Could not load TFLite model")

    @property
    def available(self) -> bool:
        return self.interpreter is not None and bool(self.classes)

    def _preprocess(self, img: Image.Image) -> np.ndarray:
        img = img.resize((self.input_size, self.input_size), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.float32)
        # The exported graph ends with mobilenet_v2.preprocess_input, so it takes
        # raw 0-255 pixels. Scaling to [-1, 1] here would apply it a second time
        # and collapse every photo onto the same class (the v1.3.0 bug).
        arr = np.expand_dims(arr, axis=0)
        dtype = self.input_detail["dtype"] if self.input_detail else np.float32
        if dtype == np.uint8:
            arr = arr.astype(np.uint8)
        else:
            arr = arr.astype(np.float32)
        return arr

    # ------------------------------------------------------------ inference
    def predict(self, img: Image.Image) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError(self.load_error or "model_unavailable")
        batch = self._preprocess(img)
        with self._lock:
            self.interpreter.set_tensor(self.input_detail["index"], batch)
            self.interpreter.invoke()
            probs = np.array(self.interpreter.get_tensor(self.output_detail["index"]))[0]

        order = np.argsort(probs)[::-1][:3]
        top3 = []
        for idx in order:
            meta = self.classes[int(idx)]
            top3.append(
                {
                    "key": meta["key"],
                    "crop": meta["crop"],
                    "disease": meta["disease"],
                    "is_healthy": bool(meta.get("is_healthy", False)),
                    "confidence": float(probs[int(idx)]),
                }
            )
        return {
            "top3": top3,
            "prediction": top3[0],
            "pred_index": int(order[0]),
            "model_version": self.model_version,
        }

    # -------------------------------------------------------------- gradcam
    def _load_keras(self):
        if self._keras_model is not None or self._keras_error is not None:
            return self._keras_model
        try:
            import tensorflow as tf

            if not settings.keras_file.exists():
                raise FileNotFoundError(str(settings.keras_file))
            self._keras_model = tf.keras.models.load_model(str(settings.keras_file))
        except Exception as exc:
            self._keras_error = str(exc)
            logger.warning("Grad-CAM disabled: %s", exc)
        return self._keras_model

    def gradcam(self, raw_image: bytes, pred_index: int) -> str | None:
        if not settings.gradcam_enabled:
            return None
        model = self._load_keras()
        if model is None:
            return None
        try:
            import sys

            from ..config import REPO_ROOT

            if str(REPO_ROOT) not in sys.path:
                sys.path.insert(0, str(REPO_ROOT))
            from ml.gradcam.gradcam import gradcam_jpeg_base64

            overlay, _ = gradcam_jpeg_base64(
                raw_image, model, img_size=self.input_size, pred_index=pred_index
            )
            return overlay
        except Exception as exc:
            logger.warning("Grad-CAM failed: %s", exc)
            return None


_vision: VisionService | None = None
_vision_lock = threading.Lock()


def get_vision_service() -> VisionService:
    global _vision
    with _vision_lock:
        if _vision is None:
            _vision = VisionService()
        return _vision
