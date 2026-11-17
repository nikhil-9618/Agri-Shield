"""Export the Keras model to TensorFlow Lite for the FastAPI inference service.

    python -m ml.export.export_tflite --model ml/artifacts/agrishield_model.keras \
        --out ml/artifacts/agrishield_model.tflite

Default export is float16 (about 2x smaller than float32, negligible accuracy
loss). Use --quantize int8 for a smaller model on low-end phones; that requires
a representative dataset, provided here from the training folder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ml/artifacts/agrishield_model.keras")
    ap.add_argument("--out", default="ml/artifacts/agrishield_model.tflite")
    ap.add_argument("--quantize", choices=["none", "float16", "int8"], default="float16")
    ap.add_argument("--data", default="dataset/processed/train", help="for int8 calibration")
    args = ap.parse_args()

    model = tf.keras.models.load_model(args.model)
    img_size = int(model.input_shape[1])
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    if args.quantize == "float16":
        converter.target_spec.supported_types = [tf.float16]
    elif args.quantize == "int8":
        files = sorted(Path(args.data).rglob("*.jpg"))[:300]

        def representative_ds():
            for f in files:
                img = tf.io.decode_jpeg(tf.io.read_file(str(f)), channels=3)
                img = tf.image.resize(img, (img_size, img_size))
                x = tf.keras.applications.mobilenet_v2.preprocess_input(img)
                yield [tf.expand_dims(x, 0)]

        converter.representative_dataset = representative_ds
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
            tf.lite.OpsSet.TFLITE_BUILTINS,
        ]
        converter.inference_input_type = tf.uint8
        converter.inference_output_type = tf.float32

    tflite_bytes = converter.convert()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(tflite_bytes)

    interpreter = tf.lite.Interpreter(model_path=str(out))
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    outp = interpreter.get_output_details()[0]
    print(
        json.dumps(
            {
                "tflite": str(out),
                "size_bytes": len(tflite_bytes),
                "size_mb": round(len(tflite_bytes) / 1e6, 2),
                "input": {"shape": inp["shape"].tolist(), "dtype": str(inp["dtype"])},
                "output": {"shape": outp["shape"].tolist(), "dtype": str(outp["dtype"])},
                "quantization": args.quantize,
            },
            indent=2,
        )
    )
    (out.parent / "tflite_info.json").write_text(
        json.dumps(
            {
                "size_bytes": len(tflite_bytes),
                "input_shape": inp["shape"].tolist(),
                "input_dtype": str(inp["dtype"]),
                "output_shape": outp["shape"].tolist(),
                "output_dtype": str(outp["dtype"]),
                "quantization": args.quantize,
                "numpy_input": "float32" if args.quantize != "int8" else "uint8",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
