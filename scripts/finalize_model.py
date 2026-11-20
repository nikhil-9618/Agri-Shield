"""Ship a freshly trained model: export, calibrate, integrate, record metadata.

One command so the steps cannot drift apart:

  1. copy the Keras model and labels into `ml/artifacts/` and the app bundle
  2. export float16 TFLite to the app assets
  3. refit temperature scaling and abstention thresholds on the new validation split
  4. copy the calibration file into the app bundle
  5. write `model_metadata.json` (sizes, hashes, metrics, thresholds)

    python scripts/finalize_model.py --run ml/artifacts_v3 --data /tmp/agrishield_v3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="ml/artifacts_v3")
    ap.add_argument("--data", default="/tmp/agrishield_v3")
    ap.add_argument("--quantize", default="float16")
    args = ap.parse_args()

    run_dir = ROOT / args.run
    keras_src = run_dir / "agrishield_model.keras"
    labels_src = run_dir / "class_names.json"
    if not keras_src.exists() or not labels_src.exists():
        raise SystemExit(f"missing artifacts in {run_dir}")

    tflite_dst = ROOT / "mobile/assets/model/agrishield_model.tflite"
    labels_dst = ROOT / "mobile/assets/model/class_names.json"
    keras_dst = ROOT / "ml/artifacts/agrishield_model.keras"

    run(
        [
            sys.executable,
            "-m",
            "ml.export.export_tflite",
            "--model",
            str(keras_src),
            "--out",
            str(tflite_dst),
            "--quantize",
            args.quantize,
        ]
    )
    shutil.copy2(labels_src, labels_dst)
    shutil.copy2(labels_src, ROOT / "ml/artifacts/class_names.json")
    shutil.copy2(keras_src, keras_dst)
    shutil.copy2(run_dir / "training_report.json", ROOT / "ml/artifacts/training_report.json")
    # The FastAPI service reads ml/artifacts/agrishield_model.tflite, the app
    # bundles mobile/assets/model/. Publish the same bytes to both, or the
    # backend silently keeps serving an older model than the phone.
    shutil.copy2(tflite_dst, ROOT / "ml/artifacts/agrishield_model.tflite")
    if (tflite_dst.parent / "tflite_info.json").exists():
        shutil.copy2(tflite_dst.parent / "tflite_info.json", ROOT / "ml/artifacts/tflite_info.json")
    # Release layout expected by reports and tooling.
    models = ROOT / "models"
    models.mkdir(exist_ok=True)
    shutil.copy2(tflite_dst, models / "agri_shield_best.tflite")
    shutil.copy2(keras_dst, models / "agri_shield_best.keras")
    shutil.copy2(labels_dst, models / "class_names.json")

    # Refit calibration on the new validation split, in place.
    run(
        [
            sys.executable,
            "-m",
            "ml.calibration.run_calibration",
            "--data",
            args.data,
            "--model",
            str(tflite_dst),
            "--labels",
            str(labels_dst),
            "--out",
            str(ROOT / "ml/artifacts/calibration.json"),
        ]
    )
    shutil.copy2(ROOT / "ml/artifacts/calibration.json", ROOT / "mobile/assets/model/calibration.json")

    report = json.loads((run_dir / "training_report.json").read_text())
    calibration = json.loads((ROOT / "ml/artifacts/calibration.json").read_text())
    metadata = {
        "model": report.get("model"),
        "arch": report.get("arch"),
        "input_size": report.get("input_size"),
        "class_count": report.get("class_count"),
        "trained_at_utc": report.get("trained_at_utc"),
        "files": {
            "keras": {
                "path": "ml/artifacts/agrishield_model.keras",
                "bytes": keras_dst.stat().st_size,
                "sha256": sha256(keras_dst),
            },
            "tflite": {
                "path": "mobile/assets/model/agrishield_model.tflite",
                "bytes": tflite_dst.stat().st_size,
                "sha256": sha256(tflite_dst),
            },
        },
        "metrics": {
            "val": report.get("val"),
            "test": report.get("test"),
            "best_val_macro_f1": report.get("best_val_macro_f1"),
            "latency_ms_batch1_cpu": report.get("latency_ms_batch1_cpu"),
        },
        "calibration": {
            "temperature": calibration["temperature"],
            "min_confidence": calibration["min_confidence"],
            "healthy_confidence": calibration["healthy_confidence"],
            "validation_ece": calibration["validation"]["calibrated"]["ece"],
            "test_ece": calibration["test"]["calibrated"]["ece"],
            "test_precision_at_threshold": calibration["test"]["calibrated"]["precision_at_threshold"],
            "test_coverage_at_threshold": calibration["test"]["calibrated"]["coverage_at_threshold"],
        },
        "training_data": {
            "dataset": report.get("dataset"),
            "sources": ["PlantVillage (lab)", "PlantDoc (field, CC-BY-4.0)"],
            "external_field_validation": "Digital Green Crop Disease Images (CC-BY-4.0)",
        },
    }
    out = ROOT / "mobile/assets/model/model_metadata.json"
    out.write_text(json.dumps(metadata, indent=2))
    shutil.copy2(out, ROOT / "models/model_metadata.json")
    print(json.dumps(metadata["metrics"], indent=2))
    print(json.dumps(metadata["calibration"], indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
