"""Fit temperature scaling and abstention thresholds, then write them out.

    python -m ml.calibration.run_calibration --data /tmp/agrishield_v2 \
        --model mobile/assets/model/agrishield_model.tflite \
        --labels mobile/assets/model/class_names.json \
        --out ml/artifacts/calibration.json

The temperature and thresholds are fitted on the *validation* split only; the
test split is used purely to report whether calibration generalised. Nothing is
copied from the test split into the shipped numbers.

Reported metrics:
  * NLL and ECE before/after temperature scaling (accuracy must not change)
  * precision/coverage of the chosen abstention threshold
  * the same metrics on the held-out test split
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.calibration.calibration import (  # noqa: E402
    apply_temperature,
    expected_calibration_error,
    fit_temperature,
    select_healthy_threshold,
    select_thresholds,
)
from ml.training.labels import class_directory_name  # noqa: E402


def collect(split_dir: Path, interpreter, inp, out, class_names: list[str], size: int):
    """Run the TFLite model over a split directory; return probs and true indices."""
    probs: list[np.ndarray] = []
    truth: list[int] = []
    for index, name in enumerate(class_names):
        # Splits are stored under the filesystem-safe class folder name, which
        # is not the raw PlantVillage label ("Apple___Apple_scab" ->
        # "Apple_Apple_scab").
        folder = split_dir / class_directory_name(name)
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue
            arr = np.asarray(
                Image.open(path).convert("RGB").resize((size, size), Image.BILINEAR),
                dtype=np.float32,
            )
            interpreter.set_tensor(inp["index"], arr.reshape(1, size, size, 3))
            interpreter.invoke()
            probs.append(np.asarray(interpreter.get_tensor(out["index"]))[0])
            truth.append(index)
    if not probs:
        raise SystemExit(f"no images found under {split_dir}")
    return np.stack(probs), np.asarray(truth, dtype=np.int64)


def negative_log_likelihood(probs: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(probs, 1e-12, None)
    return float(-np.log(p[np.arange(len(y)), y]).mean())


def summarise(probs: np.ndarray, y: np.ndarray, threshold: float) -> dict:
    conf = probs.max(axis=1)
    correct = probs.argmax(axis=1) == y
    accepted = conf >= threshold
    return {
        "n": int(len(y)),
        "accuracy": round(float(correct.mean()), 4),
        "nll": round(negative_log_likelihood(probs, y), 4),
        "ece": round(expected_calibration_error(probs, y), 4),
        "mean_confidence": round(float(conf.mean()), 4),
        "coverage_at_threshold": round(float(accepted.mean()), 4),
        "precision_at_threshold": round(float(correct[accepted].mean()), 4)
        if accepted.any()
        else None,
        "confident_wrong_rate": round(
            float((~correct & (conf >= 0.80)).mean()), 4
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/agrishield_v2")
    ap.add_argument("--model", default="mobile/assets/model/agrishield_model.tflite")
    ap.add_argument("--labels", default="mobile/assets/model/class_names.json")
    ap.add_argument("--out", default="ml/artifacts/calibration.json")
    # 0.98, not 0.90: at 0.90 the gate accepts 98% of photos and almost never
    # abstains, which is the behaviour we are trying to replace.
    ap.add_argument("--target-precision", type=float, default=0.98)
    ap.add_argument("--min-coverage", type=float, default=0.60)
    args = ap.parse_args()

    from ai_edge_litert.interpreter import Interpreter

    root = Path(args.data)
    labels = json.loads(Path(args.labels).read_text("utf-8"))
    class_names = [c["label"] for c in sorted(labels, key=lambda c: c["index"])]
    class_keys = [c["key"] for c in sorted(labels, key=lambda c: c["index"])]
    healthy_keys = [c["key"] for c in labels if c.get("is_healthy")]

    it = Interpreter(model_path=args.model)
    it.allocate_tensors()
    inp, out = it.get_input_details()[0], it.get_output_details()[0]
    size = int(inp["shape"][1])
    if int(out["shape"][-1]) != len(class_names):
        raise SystemExit(
            f"model outputs {out['shape'][-1]} classes but labels have {len(class_names)}"
        )

    started = time.time()
    print("scoring validation split...", flush=True)
    val_probs, val_y = collect(root / "val", it, inp, out, class_names, size)
    print("scoring test split...", flush=True)
    test_probs, test_y = collect(root / "test", it, inp, out, class_names, size)

    temperature = fit_temperature(val_probs, val_y)
    val_cal = apply_temperature(val_probs, temperature)
    test_cal = apply_temperature(test_probs, temperature)

    abstain = select_thresholds(
        val_cal,
        val_y,
        class_keys,
        healthy_keys,
        target_precision=args.target_precision,
        min_coverage=args.min_coverage,
    )
    healthy = select_healthy_threshold(
        val_cal, val_y, class_keys, healthy_keys, base_threshold=abstain["threshold"]
    )

    # Accuracy is invariant under temperature scaling; assert it rather than assume.
    before = int((val_probs.argmax(axis=1) == val_y).sum())
    after = int((val_cal.argmax(axis=1) == val_y).sum())
    if before != after:
        raise SystemExit(f"temperature scaling changed predictions ({before} vs {after})")

    report = {
        "fitted_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "temperature scaling on the validation split (NLL minimisation)",
        "model": args.model,
        "class_count": len(class_names),
        "temperature": temperature,
        "min_confidence": abstain["threshold"],
        "healthy_confidence": healthy["threshold"],
        "abstention": abstain,
        "healthy_rule": healthy,
        "validation": {
            "uncalibrated": summarise(val_probs, val_y, abstain["threshold"]),
            "calibrated": summarise(val_cal, val_y, abstain["threshold"]),
        },
        "test": {
            "uncalibrated": summarise(test_probs, test_y, abstain["threshold"]),
            "calibrated": summarise(test_cal, test_y, abstain["threshold"]),
        },
        "notes": [
            "Temperature scaling never changes the predicted class, only the confidence.",
            "min_confidence is the lowest confidence that kept accepted-set precision at the target on validation.",
            "healthy_confidence is stricter because a false 'healthy' verdict stops treatment.",
            "Field photos remain out of distribution; these numbers are PlantVillage-only.",
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), "utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"notes"}}, indent=2))
    print(f"\nwrote {out_path} in {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
