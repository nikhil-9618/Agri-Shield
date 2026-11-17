"""Train the AgriShield leaf-disease classifier (MobileNetV2 transfer learning).

CPU-friendly default: 128x128 input, frozen ImageNet backbone for the first
phase, then a short fine-tune of the last block. The shipped model was produced
with exactly this script (see documentation/MODEL_CARD.md).

    python -m ml.training.train --data /tmp/agrishield_dataset --out ml/artifacts

Artifacts written to --out:
    agrishield_model.keras     full Keras model (used for Grad-CAM)
    class_names.json           index -> class metadata (single source of truth)
    training_report.json       config, history, dataset manifest summary
    best_checkpoint.keras      best validation-accuracy epoch
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.training.labels import class_directory_name, classify, supported_class_indices, CLASS_NAMES  # noqa: E402

AUTOTUNE = tf.data.AUTOTUNE


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
    return ds.prefetch(AUTOTUNE)


def build_model(img_size: int, n_classes: int, dropout: float, l2: float):
    augment = tf.keras.Sequential(
        [
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.12),
            layers.RandomZoom(0.12),
            layers.RandomContrast(0.12),
            layers.RandomTranslation(0.06, 0.06),
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
    x = layers.Dense(
        256,
        activation="relu",
        kernel_regularizer=tf.keras.regularizers.l2(l2),
        name="embedding",
    )(x)
    x = layers.Dropout(dropout)(x)
    outputs = layers.Dense(n_classes, activation="softmax", name="disease")(x)
    return models.Model(inputs, outputs, name="agrishield_mobilenetv2"), base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset/processed")
    ap.add_argument("--out", default="ml/artifacts")
    ap.add_argument("--img-size", type=int, default=128)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--head-epochs", type=int, default=4)
    ap.add_argument("--finetune-epochs", type=int, default=2)
    ap.add_argument("--finetune-layers", type=int, default=24)
    ap.add_argument("--head-lr", type=float, default=1e-3)
    ap.add_argument("--finetune-lr", type=float, default=1e-4)
    ap.add_argument("--dropout", type=float, default=0.25)
    ap.add_argument("--l2", type=float, default=1e-4)
    args = ap.parse_args()

    data_root = Path(args.data)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    class_names = sorted(p.name for p in (data_root / "train").iterdir() if p.is_dir())
    raw_by_dir = {class_directory_name(c): c for c in CLASS_NAMES}
    metadata = [classify(raw_by_dir[name]) for name in class_names]
    class_index = [{"index": i, **meta} for i, meta in enumerate(metadata)]
    (out / "class_names.json").write_text(json.dumps(class_index, indent=2))
    print(f"{len(class_names)} classes: {class_names}")

    train_ds = load_split(data_root, "train", args.img_size, args.batch, class_names, True)
    val_ds = load_split(data_root, "val", args.img_size, args.batch, class_names, False)

    model, base = build_model(args.img_size, len(class_names), args.dropout, args.l2)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(args.head_lr),
        loss="categorical_crossentropy",
        metrics=[
            "accuracy",
            tf.keras.metrics.TopKCategoricalAccuracy(k=3, name="top3_accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ],
    )
    model.summary()

    ckpt = out / "best_checkpoint.keras"
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(str(ckpt), monitor="val_accuracy", save_best_only=True, verbose=1),
        tf.keras.callbacks.CSVLogger(str(out / "training_log.csv")),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.4, patience=1, min_lr=1e-6),
        tf.keras.callbacks.TerminateOnNaN(),
    ]

    t0 = time.time()
    history: dict[str, list[float]] = {}
    h1 = model.fit(train_ds, validation_data=val_ds, epochs=args.head_epochs, callbacks=callbacks)
    for k, v in h1.history.items():
        history[k] = [float(x) for x in v]

    # ---- fine-tune the top of the backbone --------------------------------
    base.trainable = True
    for layer in base.layers[: -args.finetune_layers]:
        layer.trainable = False
    model.compile(
        optimizer=tf.keras.optimizers.Adam(args.finetune_lr),
        loss="categorical_crossentropy",
        metrics=[
            "accuracy",
            tf.keras.metrics.TopKCategoricalAccuracy(k=3, name="top3_accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
        ],
    )
    h2 = model.fit(train_ds, validation_data=val_ds, epochs=args.finetune_epochs, callbacks=callbacks)
    for k, v in h2.history.items():
        history.setdefault(k, []).extend(float(x) for x in v)

    model.save(out / "agrishield_model.keras")
    best = model.evaluate(val_ds, return_dict=True)
    report = {
        "model": "MobileNetV2 (ImageNet) + GAP/Dense head, transfer learning",
        "input_size": args.img_size,
        "classes": class_index,
        "dataset": json.loads((data_root / "dataset_manifest.json").read_text())
        if (data_root / "dataset_manifest.json").exists()
        else None,
        "config": vars(args),
        "history": history,
        "final_val_metrics": best,
        "train_seconds": round(time.time() - t0, 1),
        "tensorflow": tf.__version__,
        "numpy": np.__version__,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "training_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"saved model -> {out / 'agrishield_model.keras'}")
    print(json.dumps(best, indent=2, default=str))


if __name__ == "__main__":
    main()
