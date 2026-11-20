"""Evaluate a trained model on internal and external data, separately.

Internal test  : PlantVillage lab images (the number that flatters the model).
External field : PlantDoc's held-out test folder (web-scraped field photos,
                 mapped onto our taxonomy, never trained on).

The two are reported in separate sections on purpose. Mixing them produces a
number that describes neither.

    python -m ml.evaluation.evaluate --model ml/artifacts_v3/agrishield_model.keras \
        --data /tmp/agrishield_v3 --plantdoc-test /tmp/plantdoc/test \
        --out reports/evaluation_report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
from PIL import Image
from sklearn.metrics import classification_report, confusion_matrix, f1_score

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.datasets.build_unified import PLANTDOC_MAP  # noqa: E402
from ml.training.labels import class_directory_name  # noqa: E402


def load_predictor(model_path: Path, img_size: int):
    """Return (predict_fn, kind). TFLite is preferred for reported numbers."""
    if model_path.suffix == ".tflite":
        from ai_edge_litert.interpreter import Interpreter

        it = Interpreter(model_path=str(model_path))
        it.allocate_tensors()
        inp, out = it.get_input_details()[0], it.get_output_details()[0]

        def predict(arr: np.ndarray) -> np.ndarray:
            it.set_tensor(inp["index"], arr[None, ...].astype(np.float32))
            it.invoke()
            return np.asarray(it.get_tensor(out["index"]))[0]

        return predict, "tflite"

    import tensorflow as tf

    model = tf.keras.models.load_model(model_path)

    def predict(arr: np.ndarray) -> np.ndarray:
        return model.predict(arr[None, ...], verbose=0)[0]

    return predict, "keras"


def score_dir(directory: Path, predict, class_names: list[str], class_keys: list[str], img_size: int):
    """Label every image in a class-folder directory and score it."""
    truth, preds, probs = [], [], []
    per_source: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for index, folder_name in enumerate(class_names):
        folder = directory / folder_name
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue
            arr = np.asarray(
                Image.open(path).convert("RGB").resize((img_size, img_size), Image.BILINEAR),
                dtype=np.float32,
            )
            p = predict(arr)
            preds.append(int(np.argmax(p)))
            probs.append(p)
            truth.append(index)
            source = "plantdoc" if path.name.startswith("plantdoc_") else "plantvillage"
            per_source[source][0] += 1
            per_source[source][1] += int(np.argmax(p) == index)
    if not truth:
        return None
    truth_arr, pred_arr = np.asarray(truth), np.asarray(preds)
    probs_arr = np.stack(probs)
    top3 = np.argsort(probs_arr, axis=1)[:, ::-1][:, :3]
    return {
        "n": len(truth),
        "accuracy": round(float((pred_arr == truth_arr).mean()), 4),
        "top3_accuracy": round(float(np.any(top3 == truth_arr[:, None], axis=1).mean()), 4),
        "macro_f1": round(float(f1_score(truth_arr, pred_arr, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(truth_arr, pred_arr, average="weighted", zero_division=0)), 4),
        "per_class": {
            class_keys[i]: {
                "n": int((truth_arr == i).sum()),
                "recall": round(float((pred_arr[truth_arr == i] == i).mean()), 4)
                if (truth_arr == i).any()
                else None,
            }
            for i in range(len(class_names))
        },
        "by_source": {
            source: {"n": n, "accuracy": round(correct / n, 4)}
            for source, (n, correct) in per_source.items()
        },
        "confusion": confusion_matrix(truth_arr, pred_arr, labels=list(range(len(class_names)))).tolist(),
        "report_text": classification_report(
            truth_arr,
            pred_arr,
            labels=list(range(len(class_names))),
            target_names=class_keys,
            zero_division=0,
        ),
    }


def score_plantdoc_test(
    directory: Path, predict, class_keys: list[str], img_size: int
) -> dict | None:
    """PlantDoc's own test folder, mapped onto our classes."""
    key_index = {k: i for i, k in enumerate(class_keys)}
    truth, preds = [], []
    for folder in sorted(directory.iterdir()):
        key = PLANTDOC_MAP.get(folder.name)
        if key is None or key not in key_index or not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue
            arr = np.asarray(
                Image.open(path).convert("RGB").resize((img_size, img_size), Image.BILINEAR),
                dtype=np.float32,
            )
            truth.append(key_index[key])
            preds.append(int(np.argmax(predict(arr))))
    if not truth:
        return None
    truth_arr, pred_arr = np.asarray(truth), np.asarray(preds)
    per_class = {}
    for key in sorted({class_keys[i] for i in truth_arr}):
        idx = key_index[key]
        mask = truth_arr == idx
        per_class[key] = {
            "n": int(mask.sum()),
            "recall": round(float((pred_arr[mask] == idx).mean()), 3),
        }
    return {
        "n": len(truth),
        "accuracy": round(float((pred_arr == truth_arr).mean()), 3),
        "macro_f1": round(float(f1_score(truth_arr, pred_arr, average="macro", zero_division=0)), 3),
        "per_class": per_class,
    }


def markdown(
    internal: dict, external: dict | None, model_name: str, img_size: int
) -> str:
    lines = [
        "# Evaluation report",
        "",
        f"Model: `{model_name}` · input {img_size}×{img_size} · generated by `ml/evaluation/evaluate.py`",
        "",
        "## Internal test — PlantVillage lab images",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Images | {internal['n']} |",
        f"| Top-1 accuracy | **{internal['accuracy']:.3f}** |",
        f"| Top-3 accuracy | {internal['top3_accuracy']:.3f} |",
        f"| Macro F1 | {internal['macro_f1']:.3f} |",
        f"| Weighted F1 | {internal['weighted_f1']:.3f} |",
        "",
        "| Source | Images | Top-1 |",
        "| --- | --- | --- |",
    ]
    for source, stats in sorted(internal["by_source"].items()):
        lines.append(f"| {source} | {stats['n']} | {stats['accuracy']:.3f} |")

    weak = sorted(
        ((k, v) for k, v in internal["per_class"].items() if v["n"] and v["recall"] is not None),
        key=lambda kv: kv[1]["recall"],
    )[:10]
    lines += ["", "### Weakest classes by recall (internal test)", "", "| Class | Images | Recall |", "| --- | --- | --- |"]
    for key, stats in weak:
        lines.append(f"| `{key}` | {stats['n']} | {stats['recall']:.3f} |")

    lines += ["", "## External field test — PlantDoc held-out", ""]
    if not external:
        lines.append("PlantDoc test data was not available for this run.")
    else:
        lines += [
            "| Metric | Value |",
            "| --- | --- |",
            f"| Images | {external['n']} |",
            f"| Top-1 accuracy | **{external['accuracy']:.3f}** |",
            f"| Macro F1 | {external['macro_f1']:.3f} |",
            "",
            "| Class | Images | Recall |",
            "| --- | --- | --- |",
        ]
        for key, stats in sorted(external["per_class"].items()):
            lines.append(f"| `{key}` | {stats['n']} | {stats['recall']:.3f} |")
        lines += [
            "",
            "These photos are web-scraped field images, counted only where our taxonomy has",
            "a matching class. They were never in training or validation.",
        ]
    lines += ["", "## Full classification report (internal test)", "", "```", internal["report_text"], "```", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ml/artifacts_v3/agrishield_model.tflite")
    ap.add_argument("--data", default="/tmp/agrishield_v3")
    ap.add_argument("--plantdoc-test", default="/tmp/plantdoc/test")
    ap.add_argument("--labels", default="ml/artifacts_v3/class_names.json")
    ap.add_argument("--img-size", type=int, default=128)
    ap.add_argument("--out", default="reports/evaluation_report.md")
    ap.add_argument("--json", default="reports/evaluation.json")
    args = ap.parse_args()

    labels = json.loads(Path(args.labels).read_text())
    ordered = sorted(labels, key=lambda c: c["index"])
    class_keys = [c["key"] for c in ordered]
    # Split folders are lower-cased by the dataset builder.
    class_names = [class_directory_name(c["label"]).lower() for c in ordered]

    predict, kind = load_predictor(Path(args.model), args.img_size)
    internal = score_dir(Path(args.data) / "test", predict, class_names, class_keys, args.img_size)
    if internal is None:
        raise SystemExit("no internal test images found")
    external = (
        score_plantdoc_test(Path(args.plantdoc_test), predict, class_keys, args.img_size)
        if Path(args.plantdoc_test).is_dir()
        else None
    )

    payload = {
        "model": args.model,
        "kind": kind,
        "image_size": args.img_size,
        "internal_test": {k: v for k, v in internal.items() if k not in {"confusion", "report_text"}},
        "external_field_test": external,
        "confusion_matrix": internal["confusion"],
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(payload, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(markdown(internal, external, args.model, args.img_size))

    print(
        f"internal: n={internal['n']} top1={internal['accuracy']:.4f} macroF1={internal['macro_f1']:.4f}"
    )
    if external:
        print(
            f"external (PlantDoc): n={external['n']} top1={external['accuracy']:.4f} "
            f"macroF1={external['macro_f1']:.4f}"
        )
    print(f"wrote {args.out} and {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
