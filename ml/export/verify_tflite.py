"""Verify an exported TFLite model against the Keras source.

Checks, in order:
  * tensor details (dtype, shape) and file size
  * the graph reacts to its input (a dead model still parses)
  * Keras and TFLite agree on the predicted class for a deterministic sample
  * the TFLite file's output count matches the label file

Writes ``reports/keras_tflite_parity_report.md`` and exits non-zero when parity
falls below the threshold, so a broken export cannot be released silently.

    python -m ml.export.verify_tflite \
        --keras ml/artifacts_v3/agrishield_model.keras \
        --tflite mobile/assets/model/agrishield_model.tflite \
        --labels mobile/assets/model/class_names.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
from PIL import Image


def sample_paths(root: Path, limit: int) -> list[Path]:
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if len(files) <= limit:
        return files
    step = len(files) / limit
    return [files[int(i * step)] for i in range(limit)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keras", default="ml/artifacts_v3/agrishield_model.keras")
    ap.add_argument("--tflite", default="mobile/assets/model/agrishield_model.tflite")
    ap.add_argument("--labels", default="mobile/assets/model/class_names.json")
    ap.add_argument("--data", default="/tmp/agrishield_v3/test")
    ap.add_argument("--samples", type=int, default=400)
    ap.add_argument("--min-agreement", type=float, default=0.99)
    ap.add_argument("--out", default="reports/keras_tflite_parity_report.md")
    args = ap.parse_args()

    import tensorflow as tf
    from ai_edge_litert.interpreter import Interpreter

    tflite_path = Path(args.tflite)
    keras_path = Path(args.keras)
    labels = json.loads(Path(args.labels).read_text())

    it = Interpreter(model_path=str(tflite_path))
    it.allocate_tensors()
    inp, out = it.get_input_details()[0], it.get_output_details()[0]
    size = int(inp["shape"][1])

    model = tf.keras.models.load_model(keras_path)
    files = sample_paths(Path(args.data), args.samples)
    if not files:
        raise SystemExit(f"no parity images under {args.data}")

    agree = 0
    max_prob_diff = 0.0
    mismatches = []
    for path in files:
        arr = np.asarray(
            Image.open(path).convert("RGB").resize((size, size), Image.BILINEAR),
            dtype=np.float32,
        )
        keras_p = model.predict(arr[None, ...], verbose=0)[0]
        it.set_tensor(inp["index"], arr[None, ...].astype(np.float32))
        it.invoke()
        tflite_p = np.asarray(it.get_tensor(out["index"]))[0]
        if int(keras_p.argmax()) == int(tflite_p.argmax()):
            agree += 1
        else:
            mismatches.append(
                {
                    "image": str(path),
                    "keras": labels[int(keras_p.argmax())]["key"],
                    "tflite": labels[int(tflite_p.argmax())]["key"],
                }
            )
        max_prob_diff = max(max_prob_diff, float(np.abs(keras_p - tflite_p).max()))

    # Input sensitivity: an exported graph that ignores its input would still
    # pass shape checks.
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 256, (1, size, size, 3)).astype(np.float32)
    it.set_tensor(inp["index"], noise)
    it.invoke()
    p_noise = np.asarray(it.get_tensor(out["index"]))[0]
    it.set_tensor(inp["index"], np.zeros_like(noise))
    it.invoke()
    p_black = np.asarray(it.get_tensor(out["index"]))[0]
    sensitivity = float(np.abs(p_noise - p_black).max())

    # Latency on this CPU, single image, median of 20.
    times = []
    it.set_tensor(inp["index"], noise)
    for _ in range(20):
        start = time.perf_counter()
        it.invoke()
        times.append((time.perf_counter() - start) * 1000)
    latency = float(np.median(times))

    rate = agree / len(files)
    passed = rate >= args.min_agreement and sensitivity > 1e-3
    report = [
        "# Keras → TFLite parity report",
        "",
        "| Check | Value |",
        "| --- | --- |",
        f"| Keras source | `{keras_path}` |",
        f"| TFLite file | `{tflite_path}` |",
        f"| TFLite size | {tflite_path.stat().st_size:,} bytes ({tflite_path.stat().st_size/1e6:.2f} MB) |",
        f"| Input | {inp['shape'].tolist()} {np.dtype(inp['dtype']).name} |",
        f"| Output | {out['shape'].tolist()} {np.dtype(out['dtype']).name} |",
        f"| Output classes vs labels | {int(out['shape'][-1])} vs {len(labels)} |",
        f"| Parity images | {len(files)} |",
        f"| Top-1 agreement | **{rate:.4f}** (required ≥ {args.min_agreement}) |",
        f"| Max probability difference | {max_prob_diff:.5f} |",
        f"| Input sensitivity | {sensitivity:.5f} |",
        f"| Single-image CPU latency | {latency:.1f} ms |",
        f"| Result | {'**PASS**' if passed else '**FAIL**'} |",
        "",
        f"Mismatches on {len(mismatches)} image(s).",
    ]
    if mismatches:
        report += ["", "| Image | Keras | TFLite |", "| --- | --- | --- |"]
        for m in mismatches[:20]:
            report.append(f"| {m['image']} | `{m['keras']}` | `{m['tflite']}` |")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report) + "\n")
    print("\n".join(report[:18]))
    print(f"\nwrote {out_path}")
    return 0 if passed else 5


if __name__ == "__main__":
    raise SystemExit(main())
