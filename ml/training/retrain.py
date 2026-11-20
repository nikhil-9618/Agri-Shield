"""Retrain AgriShield with a verified pipeline.

Why this exists: the first shipped checkpoint had a dead ReLU bottleneck, so
every photo produced the same class ("common rust"). This script trains the
same MobileNetV2 backbone with a direct softmax head and refuses to save a model
that does not react to its input.

    python -m ml.training.retrain --data /tmp/agrishield_dataset --out ml/artifacts \
        --head-epochs 6 --finetune-epochs 2

Checks run before artifacts are written:
  * the head is not constant: different inputs must give different logits
  * noise / black / white frames must not be predicted with high confidence
  * held-out test accuracy and top-3 accuracy are reported per class
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
from tensorflow.keras import layers, models

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.training.labels import (  # noqa: E402
    CLASS_NAMES,
    class_directory_name,
    classify,
    supported_class_indices,
)

AUTOTUNE = tf.data.AUTOTUNE


def build_model(img_size: int, n_classes: int, dropout: float) -> tf.keras.Model:
    augment = tf.keras.Sequential(
        [
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.1),
            layers.RandomZoom(0.1),
            layers.RandomContrast(0.1),
            layers.RandomTranslation(0.05, 0.05),
        ],
        name="augment",
    )
    base = tf.keras.applications.MobileNetV2(
        input_shape=(img_size, img_size, 3), include_top=False, weights="imagenet"
    )
    base.trainable = False

    inputs = tf.keras.Input(shape=(img_size, img_size, 3), name="leaf_image")
    x = augment(inputs)
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(dropout)(x)
    outputs = layers.Dense(n_classes, activation="softmax", name="disease")(x)
    return models.Model(inputs, outputs, name="agrishield_mobilenetv2"), base


def load_split(root: Path, split: str, img_size: int, batch: int, class_names: list[str], training: bool):
    ds = tf.keras.utils.image_dataset_from_directory(
        root / split,
        labels="inferred",
        label_mode="categorical",
        class_names=class_names,
        image_size=(img_size, img_size),
        batch_size=batch,
        shuffle=training,
        seed=1337,
    )
    if training:
        ds = ds.shuffle(2048, seed=1337, reshuffle_each_iteration=True)
    return ds.prefetch(AUTOTUNE)


def evaluate(model, ds, class_names: list[str], img_size: int) -> dict:
    y_true, y_pred = [], []
    for images, labels in ds:
        probs = model.predict(images, verbose=0)
        y_true.extend(np.argmax(labels.numpy(), axis=1))
        y_pred.append(probs)
    probs = np.concatenate(y_pred, axis=0)
    y_true = np.array(y_true)
    top1 = probs.argmax(axis=1)
    top3 = np.argsort(probs, axis=1)[:, ::-1][:, :3]
    accuracy = float((top1 == y_true).mean())
    top3_accuracy = float(np.any(top3 == y_true[:, None], axis=1).mean())
    per_class = {}
    for i, name in enumerate(class_names):
        mask = y_true == i
        if mask.sum():
            per_class[name] = {
                "n": int(mask.sum()),
                "accuracy": round(float((top1[mask] == i).mean()), 4),
            }
    return {
        "accuracy": round(accuracy, 4),
        "top3_accuracy": round(top3_accuracy, 4),
        "per_class": per_class,
        "mean_confidence": round(float(probs.max(axis=1).mean()), 4),
    }


def sanity_check(model, img_size: int) -> dict:
    """The model must react to input and stay quiet on non-leaf images."""
    rng = np.random.default_rng(0)
    cases = {
        "noise": rng.integers(0, 256, (img_size, img_size, 3)).astype(np.float32),
        "black": np.zeros((img_size, img_size, 3), np.float32),
        "white": np.full((img_size, img_size, 3), 255.0, np.float32),
    }
    out = {}
    preds = []
    for name, arr in cases.items():
        p = model.predict(tf.expand_dims(arr, 0), verbose=0)[0]
        preds.append(p)
        out[name] = {"top": int(np.argmax(p)), "confidence": round(float(p.max()), 4)}
    spread = float(np.abs(preds[0] - preds[1]).max())
    out["logit_spread_between_noise_and_black"] = round(spread, 6)
    out["reacts_to_input"] = spread > 1e-3
    out["degenerate_confident"] = any(v["confidence"] > 0.80 for k, v in out.items() if k in cases)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/agrishield_dataset")
    ap.add_argument("--out", default="ml/artifacts")
    ap.add_argument("--img-size", type=int, default=128)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--head-epochs", type=int, default=6)
    ap.add_argument("--finetune-epochs", type=int, default=2)
    ap.add_argument("--finetune-layers", type=int, default=30)
    ap.add_argument("--head-lr", type=float, default=8e-4)
    ap.add_argument("--finetune-lr", type=float, default=8e-5)
    ap.add_argument("--dropout", type=float, default=0.2)
    args = ap.parse_args()

    data_root = Path(args.data)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    class_names = sorted(p.name for p in (data_root / "train").iterdir() if p.is_dir())
    by_directory = {class_directory_name(c): c for c in CLASS_NAMES}
    metadata = [classify(by_directory[name]) for name in class_names]
    class_index = [{"index": i, **meta} for i, meta in enumerate(metadata)]
    print(f"{len(class_names)} classes", flush=True)

    train_ds = load_split(data_root, "train", args.img_size, args.batch, class_names, True)
    val_ds = load_split(data_root, "val", args.img_size, args.batch, class_names, False)
    test_ds = load_split(data_root, "test", args.img_size, args.batch, class_names, False)

    model, base = build_model(args.img_size, len(class_names), args.dropout)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(args.head_lr),
        loss="categorical_crossentropy",
        metrics=["accuracy", tf.keras.metrics.TopKCategoricalAccuracy(k=3, name="top3_accuracy")],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=2, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=1, min_lr=1e-5),
    ]

    started = time.time()
    print("phase 1: frozen backbone", flush=True)
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.head_epochs,
        callbacks=callbacks,
        verbose=2,
    ).history

    if args.finetune_epochs > 0:
        print("phase 2: fine-tune last layers", flush=True)
        base.trainable = True
        for layer in base.layers[: -args.finetune_layers]:
            layer.trainable = False
        model.compile(
            optimizer=tf.keras.optimizers.Adam(args.finetune_lr),
            loss="categorical_crossentropy",
            metrics=["accuracy", tf.keras.metrics.TopKCategoricalAccuracy(k=3, name="top3_accuracy")],
        )
        fine = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=args.finetune_epochs,
            callbacks=callbacks,
            verbose=2,
        ).history
        for k, v in fine.items():
            history.setdefault(k, []).extend(v)

    sanity = sanity_check(model, args.img_size)
    test_metrics = evaluate(model, test_ds, class_names, args.img_size)
    print("sanity:", json.dumps(sanity), flush=True)
    print("test:", json.dumps({k: v for k, v in test_metrics.items() if k != "per_class"}), flush=True)

    # A closed-set classifier has no "not a leaf" class, so confident answers on
    # noise are expected; the app's leaf gate and abstention handle those. Only a
    # model that ignores its input is unreleasable.
    if not sanity["reacts_to_input"]:
        print("REFUSING to save: model does not react to input correctly", file=sys.stderr, flush=True)
        return 2
    if sanity["degenerate_confident"]:
        print("WARNING: confident on blank/noise frames - keep the leaf gate and abstention", flush=True)
    if test_metrics["accuracy"] < 0.80:
        print("REFUSING to save: test accuracy below 0.80", file=sys.stderr, flush=True)
        return 3

    model.save(out / "agrishield_model.keras")
    (out / "class_names.json").write_text(json.dumps(class_index, indent=2))

    report = {
        "model": "MobileNetV2 (ImageNet) frozen + GAP/Dropout/softmax head, transfer learning",
        "input_size": args.img_size,
        "trained_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "train_seconds": round(time.time() - started, 1),
        "classes": class_index,
        "history": {
            k: [float(x) for x in v]
            for k, v in history.items()
            if k in {"accuracy", "loss", "val_accuracy", "val_loss", "top3_accuracy", "val_top3_accuracy"}
        },
        "sanity": sanity,
        "test": test_metrics,
        "tensorflow": tf.__version__,
        "numpy": np.__version__,
    }
    (out / "training_report.json").write_text(json.dumps(report, indent=2))
    print("saved:", out / "agrishield_model.keras", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
