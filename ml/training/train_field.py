"""Train the shipped AgriShield model on lab + field images.

This is the run that produces the released artifact. It differs from
``retrain.py`` in three ways that matter:

  * the dataset includes PlantDoc field photos (``ml/datasets/build_unified.py``),
    so the model has seen real backgrounds and lighting;
  * the checkpoint is selected by validation **macro F1**, not accuracy;
  * the training phase fine-tunes the top of the backbone, which was abandoned in
    v2 because 2 epochs at 8e-5 overfit a 27-class frozen head. Here the learning
    rate is one order lower and the head is already converged first.

Gates before anything is saved as shippable:
  * the model must react to its input (the v1.3.0 failure was a dead network);
  * test macro F1 must be at least ``--min-test-f1``;
  * test top-1 must be at least ``--min-test-accuracy``.

    python -m ml.training.train_field --data /tmp/agrishield_v3 \
        --out ml/artifacts_v3 --arch mobilenetv2 --head-epochs 10 --finetune-epochs 2
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
from sklearn.metrics import classification_report, f1_score

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.training.benchmark import build, evaluate, latency_ms, load_split  # noqa: E402
from ml.training.callbacks import MacroF1Checkpoint, standard_callbacks  # noqa: E402


def load_config(path: str | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml is in ml/requirements.txt
        return {}
    return yaml.safe_load(Path(path).read_text()) or {}


def class_weights_for(root: Path, class_names: list[str]) -> dict[int, float]:
    counts = np.array(
        [len(list((root / "train" / name).iterdir())) for name in class_names], dtype=np.float64
    )
    weights = counts.sum() / (len(counts) * np.maximum(counts, 1))
    return {i: float(w) for i, w in enumerate(weights)}


def sanity_check(model, img_size: int) -> dict:
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
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ml/training/config.yaml")
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--arch", default=None)
    ap.add_argument("--img-size", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--head-epochs", type=int, default=None)
    ap.add_argument("--finetune-epochs", type=int, default=None)
    ap.add_argument("--finetune-layers", type=int, default=None)
    ap.add_argument("--head-lr", type=float, default=None)
    ap.add_argument("--finetune-lr", type=float, default=None)
    ap.add_argument("--dropout", type=float, default=None)
    ap.add_argument("--label-smoothing", type=float, default=None)
    ap.add_argument("--class-weights", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--min-test-f1", type=float, default=0.60)
    ap.add_argument("--min-test-accuracy", type=float, default=0.80)
    args = ap.parse_args()

    cfg = load_config(args.config)
    data = Path(args.data or cfg.get("data", {}).get("root", "/tmp/agrishield_v3"))
    out = Path(args.out or cfg.get("output", {}).get("dir", "ml/artifacts_v3"))
    model_cfg = cfg.get("model", {})
    train_cfg = cfg.get("training", {})

    arch = args.arch or model_cfg.get("arch", "mobilenetv2")
    img_size = args.img_size or model_cfg.get("image_size", 128)
    batch = args.batch or train_cfg.get("batch_size", 64)
    head_epochs = args.head_epochs if args.head_epochs is not None else train_cfg.get("head_epochs", 10)
    ft_epochs = args.finetune_epochs if args.finetune_epochs is not None else train_cfg.get("fine_tune_epochs", 2)
    ft_layers = args.finetune_layers or train_cfg.get("fine_tune_layers", 40)
    head_lr = args.head_lr or train_cfg.get("head_lr", 5e-4)
    finetune_lr = args.finetune_lr or train_cfg.get("fine_tune_lr", 5e-5)
    dropout = args.dropout if args.dropout is not None else model_cfg.get("dropout", 0.2)
    smoothing = (
        args.label_smoothing
        if args.label_smoothing is not None
        else train_cfg.get("label_smoothing", 0.05)
    )
    seed = args.seed or train_cfg.get("seed", 1337)
    use_weights = args.class_weights or bool(train_cfg.get("class_weights", False))

    tf.keras.utils.set_random_seed(seed)
    out.mkdir(parents=True, exist_ok=True)

    class_names = sorted(p.name for p in (data / "train").iterdir() if p.is_dir())
    labels = json.loads(Path("ml/artifacts/class_names.json").read_text())
    labels_by_dir = {}
    from ml.training.labels import class_directory_name

    for entry in labels:
        labels_by_dir[class_directory_name(entry["label"])] = entry
    missing = [n for n in class_names if n not in labels_by_dir]
    if missing:
        raise SystemExit(f"classes without metadata: {missing[:3]}")

    train_ds = load_split(data, "train", img_size, batch, class_names, True)
    val_ds = load_split(data, "val", img_size, batch, class_names, False)
    test_ds = load_split(data, "test", img_size, batch, class_names, False)

    model, base = build(arch, img_size, len(class_names), dropout=dropout)
    weights = class_weights_for(data, class_names) if use_weights else None

    def compile_at(lr: float) -> None:
        model.compile(
            optimizer=tf.keras.optimizers.Adam(lr),
            loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=smoothing),
            metrics=["accuracy"],
        )

    compile_at(head_lr)
    best_path = out / "best.keras"
    f1_ckpt = MacroF1Checkpoint(val_ds, best_path)
    callbacks = [f1_ckpt] + standard_callbacks(out, patience=2)

    started = time.time()
    print(f"phase 1: frozen {arch} backbone, {head_epochs} epochs, {len(class_names)} classes", flush=True)
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=head_epochs,
        callbacks=callbacks,
        class_weight=weights,
        verbose=2,
    ).history

    if ft_epochs > 0:
        print(f"phase 2: fine-tune last {ft_layers} backbone layers at lr {finetune_lr}", flush=True)
        base.trainable = True
        for layer in base.layers[:-ft_layers]:
            layer.trainable = False
        compile_at(finetune_lr)
        fine = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=ft_epochs,
            callbacks=callbacks,
            class_weight=weights,
            verbose=2,
        ).history
        for key, values in fine.items():
            history.setdefault(key, []).extend(values)

    if not best_path.exists():
        raise SystemExit("no checkpoint was written; training produced no usable epoch")

    model = tf.keras.models.load_model(best_path)
    sanity = sanity_check(model, img_size)
    val_metrics = evaluate(model, val_ds)
    test_metrics = evaluate(model, test_ds)

    probs, truth = [], []
    for images, targets in test_ds:
        probs.append(model.predict(images, verbose=0))
        truth.extend(np.argmax(targets.numpy(), axis=1))
    probs = np.concatenate(probs)
    truth = np.asarray(truth)
    pred = probs.argmax(axis=1)
    report_text = classification_report(
        truth,
        pred,
        labels=list(range(len(class_names))),
        target_names=class_names,
        zero_division=0,
    )

    print("sanity:", json.dumps(sanity), flush=True)
    print(
        f"val: top1={val_metrics['accuracy']:.4f} macroF1={val_metrics['macro_f1']:.4f}\n"
        f"test: top1={test_metrics['accuracy']:.4f} top3={test_metrics['top3_accuracy']:.4f} "
        f"macroF1={test_metrics['macro_f1']:.4f}",
        flush=True,
    )

    if not sanity["reacts_to_input"]:
        print("REFUSING to save: model ignores its input", file=sys.stderr)
        return 2
    if test_metrics["macro_f1"] < args.min_test_f1:
        print(
            f"REFUSING to save: test macro F1 {test_metrics['macro_f1']:.3f} < {args.min_test_f1}",
            file=sys.stderr,
        )
        return 3
    if test_metrics["accuracy"] < args.min_test_accuracy:
        print(
            f"REFUSING to save: test top-1 {test_metrics['accuracy']:.3f} < {args.min_test_accuracy}",
            file=sys.stderr,
        )
        return 4

    model.save(out / "agrishield_model.keras")
    class_index = [
        {"index": i, **{k: v for k, v in labels_by_dir[name].items() if k != "index"}}
        for i, name in enumerate(class_names)
    ]
    (out / "class_names.json").write_text(json.dumps(class_index, indent=2))

    report = {
        "model": f"{arch} (ImageNet) + field augmentation + GAP/Dropout/softmax",
        "arch": arch,
        "input_size": img_size,
        "trained_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "train_seconds": round(time.time() - started, 1),
        "dataset": str(data),
        "class_count": len(class_names),
        "config": {
            "batch": batch,
            "head_epochs": head_epochs,
            "finetune_epochs": ft_epochs,
            "finetune_layers": ft_layers,
            "head_lr": head_lr,
            "finetune_lr": finetune_lr,
            "dropout": dropout,
            "label_smoothing": smoothing,
            "class_weights": use_weights,
            "seed": seed,
        },
        "classes": class_index,
        "history": {
            k: [float(x) for x in v]
            for k, v in history.items()
            if k in {"accuracy", "loss", "val_accuracy", "val_loss"}
        },
        "epoch_metrics": f1_ckpt.history,
        "best_val_macro_f1": f1_ckpt.best,
        "sanity": sanity,
        "val": {k: v for k, v in val_metrics.items() if k != "per_class"},
        "test": {k: v for k, v in test_metrics.items() if k != "per_class"},
        "test_per_class": test_metrics["per_class"],
        "latency_ms_batch1_cpu": latency_ms(model, img_size),
        "tensorflow": tf.__version__,
    }
    (out / "training_report.json").write_text(json.dumps(report, indent=2))
    (out / "classification_report.txt").write_text(report_text)
    print(f"saved {out/'agrishield_model.keras'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
