"""Grad-CAM explainability for the AgriShield classifier.

Produces a heatmap for the *predicted* class using the gradient of the class
score with respect to the last convolutional feature map, plus a JPEG overlay
that the API returns to the app (`gradcam_base64`).
"""

from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf


def make_gradcam_heatmap(
    img_array: np.ndarray,
    model: tf.keras.Model,
    last_conv_layer_name: str = "Conv_1",
    pred_index: int | None = None,
) -> np.ndarray:
    """img_array: (1, H, W, 3) float32, already preprocessed."""
    grad_model = tf.keras.Model(
        model.inputs,
        [model.get_layer(last_conv_layer_name).output, model.output],
    )
    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(img_array, training=False)
        if pred_index is None:
            pred_index = int(tf.argmax(predictions[0]))
        class_channel = predictions[:, pred_index]
    grads = tape.gradient(class_channel, conv_outputs)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
    conv_outputs = conv_outputs[0]
    heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)
    heatmap = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-8)
    return heatmap.numpy()


def overlay_heatmap(original_bgr: np.ndarray, heatmap: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    heatmap = cv2.resize(heatmap, (original_bgr.shape[1], original_bgr.shape[0]))
    heatmap_uint8 = np.uint8(255 * heatmap)
    colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    return cv2.addWeighted(colored, alpha, original_bgr, 1 - alpha, 0)


def gradcam_jpeg_base64(
    image_bytes: bytes,
    model: tf.keras.Model,
    img_size: int | None = None,
    last_conv_layer_name: str = "Conv_1",
    pred_index: int | None = None,
) -> tuple[str, np.ndarray]:
    """Return (base64 JPEG overlay, heatmap array) for an uploaded image."""
    if img_size is None:
        img_size = int(model.input_shape[1])
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("could not decode image")
    rgb = cv2.cvtColor(cv2.resize(bgr, (img_size, img_size)), cv2.COLOR_BGR2RGB)
    # The Keras model applies mobilenet_v2.preprocess_input internally, so it
    # expects raw 0-255 pixels here (scaling again would double-preprocess).
    batch = np.expand_dims(rgb.astype(np.float32), axis=0)
    heatmap = make_gradcam_heatmap(batch, model, last_conv_layer_name, pred_index)
    overlay = overlay_heatmap(bgr, heatmap)
    ok, buf = cv2.imencode(".jpg", overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        raise RuntimeError("failed to encode Grad-CAM overlay")
    return base64.b64encode(buf.tobytes()).decode("ascii"), heatmap


def save_heatmap_png(image_path: str | Path, model: tf.keras.Model, out_path: str | Path) -> Path:
    """CLI helper: write a Grad-CAM overlay PNG for one image."""
    image_bytes = Path(image_path).read_bytes()
    b64, _ = gradcam_jpeg_base64(image_bytes, model)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Grad-CAM overlay for one image")
    ap.add_argument("image")
    ap.add_argument("--model", default="ml/artifacts/agrishield_model.keras")
    ap.add_argument("--out", default="ml/artifacts/gradcam_example.jpg")
    a = ap.parse_args()
    m = tf.keras.models.load_model(a.model)
    print(f"wrote {save_heatmap_png(a.image, m, a.out)}")
