"""Benchmark backbone architectures at a fixed training budget.

Every candidate is trained the same way (frozen ImageNet backbone, identical
augmentation, identical epochs and learning rate) on the same unified dataset,
so the comparison is about the backbone and nothing else. Ranking is reported at
a fixed budget on the validation split, with macro F1 alongside top-1 because a
model can look good on accuracy while failing small classes.

    python -m ml.training.benchmark --data /tmp/agrishield_v3 \
        --archs mobilenetv2,mobilenetv3large,efficientnetb0,efficientnetv2b0,resnet50 \
        --epochs 3 --out reports/model_benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf
from sklearn.metrics import f1_score
from tensorflow.keras import layers, models

sys.path.append(str(Path(__file__).resolve().parents[2]))

AUTOTUNE = tf.data.AUTOTUNE

ARCHS = {
    "mobilenetv2": (tf.keras.applications.MobileNetV2, tf.keras.applications.mobilenet_v2.preprocess_input),
    "mobilenetv3large": (
        tf.keras.applications.MobileNetV3Large,
        tf.keras.applications.mobilenet_v3.preprocess_input,
    ),
    "efficientnetb0": (
        tf.keras.applications.EfficientNetB0,
        tf.keras.applications.efficientnet.preprocess_input,
    ),
    "efficientnetv2b0": (
        tf.keras.applications.EfficientNetV2B0,
        tf.keras.applications.efficientnet_v2.preprocess_input,
    ),
    "resnet50": (tf.keras.applications.ResNet50, tf.keras.applications.resnet50.preprocess_input),
}


def make_augment() -> tf.keras.Sequential:
    """Augmentation a phone photo can actually contain.

    Field photos vary in light, framing and blur, so brightness, contrast, small
    rotations/zooms and mild blur are fair. Nothing here changes the disease
    evidence (no colour inversion, no hue rotation that would turn a yellow halo
    green).
    """
    return tf.keras.Sequential(
        [
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.08, fill_mode="reflect"),
            layers.RandomZoom(0.12, fill_mode="reflect"),
            layers.RandomTranslation(0.06, 0.06, fill_mode="reflect"),
            layers.RandomBrightness(0.15),
            layers.RandomContrast(0.15),
            # Keras caps stddev at 1.0; on 0-255 pixels this is ~2.5 grey
            # levels of sensor noise, which is the point.
            layers.GaussianNoise(0.01),
        ],
        name="field_augment",
    )


def build(arch: str, img_size: int, n_classes: int, dropout: float = 0.2):
    base_fn, preprocess = ARCHS[arch]
    inputs = tf.keras.Input((img_size, img_size, 3), name="leaf_image")
    x = make_augment()(inputs)
    x = preprocess(x)
    base = base_fn(input_shape=(img_size, img_size, 3), include_top=False, weights="imagenet")
    base.trainable = False
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(dropout)(x)
    outputs = layers.Dense(n_classes, activation="softmax", name="disease")(x)
    return models.Model(inputs, outputs, name=f"agrishield_{arch}"), base


def load_split(root: Path, split: str, img_size: int, batch: int, class_names: list[str], shuffle: bool):
    ds = tf.keras.utils.image_dataset_from_directory(
        root / split,
        labels="inferred",
        label_mode="categorical",
        class_names=class_names,
        image_size=(img_size, img_size),
        batch_size=batch,
        shuffle=shuffle,
        seed=1337,
    )
    if shuffle:
        ds = ds.shuffle(2048, seed=1337, reshuffle_each_iteration=True)
    return ds.prefetch(AUTOTUNE)


def evaluate(model, ds) -> dict:
    probs, truth = [], []
    for images, labels in ds:
        probs.append(model.predict(images, verbose=0))
        truth.extend(np.argmax(labels.numpy(), axis=1))
    probs = np.concatenate(probs)
    truth = np.asarray(truth)
    top1 = probs.argmax(axis=1)
    top3 = np.argsort(probs, axis=1)[:, ::-1][:, :3]
    per_class = {}
    for i in range(probs.shape[1]):
        mask = truth == i
        if mask.any():
            per_class[i] = {
                "n": int(mask.sum()),
                "recall": round(float((top1[mask] == i).mean()), 4),
            }
    return {
        "accuracy": round(float((top1 == truth).mean()), 4),
        "top3_accuracy": round(float(np.any(top3 == truth[:, None], axis=1).mean()), 4),
        "macro_f1": round(float(f1_score(truth, top1, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(truth, top1, average="weighted", zero_division=0)), 4),
        "per_class": per_class,
    }


def latency_ms(model, img_size: int, runs: int = 15) -> float:
    batch = np.random.default_rng(0).integers(0, 256, (1, img_size, img_size, 3)).astype(np.float32)
    model.predict(batch, verbose=0)  # warm up
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        model.predict(batch, verbose=0)
        times.append((time.perf_counter() - start) * 1000)
    return round(float(np.median(times)), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/agrishield_v3")
    ap.add_argument("--archs", default="mobilenetv2,mobilenetv3large,efficientnetb0,efficientnetv2b0,resnet50")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--img-size", type=int, default=128)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", default="reports/model_benchmark.json")
    args = ap.parse_args()

    root = Path(args.data)
    class_names = sorted(p.name for p in (root / "train").iterdir() if p.is_dir())
    print(f"{len(class_names)} classes", flush=True)

    train_ds = load_split(root, "train", args.img_size, args.batch, class_names, True)
    val_ds = load_split(root, "val", args.img_size, args.batch, class_names, False)

    results = []
    for arch in [a.strip() for a in args.archs.split(",") if a.strip()]:
        print(f"\n=== {arch} ===", flush=True)
        started = time.time()
        model, base = build(arch, args.img_size, len(class_names))
        model.compile(
            optimizer=tf.keras.optimizers.Adam(args.lr),
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=args.epochs,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss", patience=1, restore_best_weights=True
                )
            ],
            verbose=2,
        ).history
        metrics = evaluate(model, val_ds)
        entry = {
            "arch": arch,
            "params_total": int(model.count_params()),
            "params_backbone": int(base.count_params()),
            "epochs_run": len(history["loss"]),
            "train_seconds": round(time.time() - started, 1),
            "val": {k: v for k, v in metrics.items() if k != "per_class"},
            "val_curve": {
                "loss": [round(float(x), 4) for x in history["loss"]],
                "val_loss": [round(float(x), 4) for x in history["val_loss"]],
                "accuracy": [round(float(x), 4) for x in history["accuracy"]],
                "val_accuracy": [round(float(x), 4) for x in history["val_accuracy"]],
            },
            "latency_ms_batch1_cpu": latency_ms(model, args.img_size),
        }
        results.append(entry)
        print(json.dumps(entry["val"]), flush=True)
        # Write after every architecture: a machine that dies mid-benchmark must
        # not lose the runs that already finished.
        write_report(Path(args.out), results, args, root)
        tf.keras.backend.clear_session()

    results.sort(key=lambda r: (-r["val"]["macro_f1"], -r["val"]["accuracy"]))
    report = {
        "dataset": str(root),
        "image_size": args.img_size,
        "epochs": args.epochs,
        "batch": args.batch,
        "learning_rate": args.lr,
        "budget_note": (
            "All backbones are frozen and trained for the same number of epochs. "
            "This ranks backbones at a fixed budget; it is not the final training run."
        ),
        "results": results,
        "best_by_macro_f1": results[0]["arch"] if results else None,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))


def write_report(out: Path, results: list[dict], args, root: Path) -> None:
    """Merge this run's results with any earlier ones already on disk."""
    merged: dict[str, dict] = {}
    if out.exists():
        try:
            for entry in json.loads(out.read_text()).get("results", []):
                merged[entry["arch"]] = entry
        except Exception:
            pass
    for entry in results:
        merged[entry["arch"]] = entry
    ordered = sorted(
        merged.values(), key=lambda r: (-r["val"]["macro_f1"], -r["val"]["accuracy"])
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "dataset": str(root),
                "image_size": args.img_size,
                "epochs": args.epochs,
                "batch": args.batch,
                "learning_rate": args.lr,
                "budget_note": (
                    "All backbones are frozen and trained for the same number of epochs. "
                    "This ranks backbones at a fixed budget; it is not the final training run. "
                    "Results are merged per architecture, so interrupted runs can resume."
                ),
                "results": ordered,
                "best_by_macro_f1": ordered[0]["arch"] if ordered else None,
            },
            indent=2,
        )
    )
    print("\nranking (macro F1):")
    for rank, r in enumerate(results, 1):
        print(
            f"{rank}. {r['arch']:<18} macroF1={r['val']['macro_f1']:.4f} "
            f"top1={r['val']['accuracy']:.4f} top3={r['val']['top3_accuracy']:.4f} "
            f"latency={r['latency_ms_batch1_cpu']}ms params={r['params_total']:,}"
        )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
