"""Evaluate the trained AgriShield model on the held-out PlantVillage test split.

Reports accuracy, macro/weighted precision, recall, F1, per-class metrics, top-3
accuracy and a confusion matrix (saved as PNG + JSON). Also evaluates the
exported TFLite file so we can prove the shipped artifact matches Keras.

    python -m ml.training.evaluate --data /tmp/agrishield_dataset \
        --model ml/artifacts/agrishield_model.keras --tflite ml/artifacts/agrishield_model.tflite
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    top_k_accuracy_score,
)


def _load(data_root: Path, split: str, img_size: int, class_names: list[str], batch: int):
    return tf.keras.utils.image_dataset_from_directory(
        data_root / split,
        labels="inferred",
        label_mode="categorical",
        class_names=class_names,
        image_size=(img_size, img_size),
        batch_size=batch,
        shuffle=False,
    )


def _collect(ds):
    y_true, y_pred, probs = [], [], []
    for images, labels in ds:
        logits = model.predict(images, verbose=0)
        probs.append(logits)
        y_pred.extend(np.argmax(logits, axis=1).tolist())
        y_true.extend(np.argmax(labels.numpy(), axis=1).tolist())
    return np.array(y_true), np.array(y_pred), np.concatenate(probs)


def _plot_confusion(cm: np.ndarray, class_names: list[str], out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(max(8, len(class_names) * 0.55), max(7, len(class_names) * 0.5)))
    im = ax.imshow(cm, interpolation="nearest", cmap="Greens")
    ax.figure.colorbar(im, ax=ax, fraction=0.035)
    ax.set(
        xticks=np.arange(len(class_names)),
        yticks=np.arange(len(class_names)),
        xticklabels=[c.replace("___", " / ") for c in class_names],
        yticklabels=[c.replace("___", " / ") for c in class_names],
        ylabel="True label",
        xlabel="Predicted label",
        title="AgriShield confusion matrix — PlantVillage held-out split",
    )
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right", fontsize=7)
    plt.setp(ax.get_yticklabels(), fontsize=7)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> None:
    global model
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset/processed")
    ap.add_argument("--split", default="test")
    ap.add_argument("--model", default="ml/artifacts/agrishield_model.keras")
    ap.add_argument("--tflite", default="ml/artifacts/agrishield_model.tflite")
    ap.add_argument("--classes", default="ml/artifacts/class_names.json")
    ap.add_argument("--out", default="ml/artifacts/evaluation")
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads(Path(args.classes).read_text())
    class_names = sorted(p.name for p in (Path(args.data) / "train").iterdir() if p.is_dir())

    model = tf.keras.models.load_model(args.model)
    img_size = int(model.input_shape[1])
    ds = _load(Path(args.data), args.split, img_size, class_names, args.batch)

    y_true, y_pred, probs = _collect(ds)
    labels = list(range(len(class_names)))
    p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    p_w, r_w, f_w, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    top3 = top_k_accuracy_score(y_true, probs, k=min(3, len(class_names)), labels=labels)

    metrics = {
        "split": args.split,
        "n_samples": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "top3_accuracy": round(float(top3), 4),
        "precision_macro": round(float(p_macro), 4),
        "recall_macro": round(float(r_macro), 4),
        "f1_macro": round(float(f_macro), 4),
        "precision_weighted": round(float(p_w), 4),
        "recall_weighted": round(float(r_w), 4),
        "f1_weighted": round(float(f_w), 4),
        "per_class": classification_report(
            y_true,
            y_pred,
            labels=labels,
            target_names=class_names,
            zero_division=0,
            output_dict=True,
        ),
        "classes": [m["label"] for m in meta],
    }

    # ---- verify the exported TFLite artifact on the same images ----------
    tflite_path = Path(args.tflite)
    if tflite_path.exists():
        interpreter = tf.lite.Interpreter(model_path=str(tflite_path), num_threads=2)
        interpreter.allocate_tensors()
        inp = interpreter.get_input_details()[0]
        outp = interpreter.get_output_details()[0]
        agreement, tflite_true, tflite_pred = 0, [], []
        total = 0
        for images, labels in ds:
            arr = images.numpy()
            if inp["dtype"] == np.uint8:
                arr_in = arr.astype(np.uint8)
            else:
                # The graph preprocesses internally; feed raw 0-255 pixels.
                arr_in = np.asarray(arr, dtype=np.float32)
            for i in range(arr.shape[0]):
                interpreter.set_tensor(inp["index"], arr_in[i : i + 1])
                interpreter.invoke()
                pred = int(np.argmax(interpreter.get_tensor(outp["index"])[0]))
                total += 1
                if pred == int(np.argmax(probs[len(tflite_pred)])):
                    agreement += 1
                tflite_pred.append(pred)
                tflite_true.append(int(np.argmax(labels[i].numpy())))
        metrics["tflite"] = {
            "file": str(tflite_path),
            "input_dtype": str(inp["dtype"]),
            "n_samples": total,
            "accuracy": round(float(accuracy_score(tflite_true, tflite_pred)), 4),
            "keras_agreement": round(agreement / max(total, 1), 4),
        }

    (out / f"metrics_{args.split}.json").write_text(json.dumps(metrics, indent=2))
    _plot_confusion(cm, class_names, out / f"confusion_matrix_{args.split}.png")
    np.savetxt(out / f"confusion_matrix_{args.split}.csv", cm, fmt="%d", delimiter=",")

    print(json.dumps({k: v for k, v in metrics.items() if k not in ("per_class",)}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
