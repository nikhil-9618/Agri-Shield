"""Callbacks used by the AgriShield training runs.

Accuracy alone hides failing classes, so the checkpoint that ships is chosen by
**validation macro F1**. That means a model cannot win a run by being good at
tomato while being useless at cherry.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import f1_score


class MacroF1Checkpoint(tf.keras.callbacks.Callback):
    """Save the model whenever validation macro F1 improves.

    Keras has no built-in metric for macro F1 over a dataset, so this evaluates
    the validation set at the end of each epoch and keeps the best weights on
    disk plus a small history file.
    """

    def __init__(self, val_ds, filepath: str | Path, verbose: int = 1) -> None:
        super().__init__()
        self.val_ds = val_ds
        self.filepath = Path(filepath)
        self.verbose = verbose
        self.best = -1.0
        self.history: list[dict] = []

    def on_epoch_end(self, epoch: int, logs: dict | None = None) -> None:
        probs, truth = [], []
        for batch_x, batch_y in self.val_ds:
            probs.append(self.model.predict(batch_x, verbose=0))
            truth.extend(np.argmax(batch_y.numpy(), axis=1))
        probs = np.concatenate(probs)
        truth = np.asarray(truth)
        pred = probs.argmax(axis=1)
        top3 = np.argsort(probs, axis=1)[:, ::-1][:, :3]
        entry = {
            "epoch": epoch + 1,
            "val_macro_f1": round(float(f1_score(truth, pred, average="macro", zero_division=0)), 4),
            "val_top1": round(float((pred == truth).mean()), 4),
            "val_top3": round(float(np.any(top3 == truth[:, None], axis=1).mean()), 4),
        }
        self.history.append(entry)
        (self.filepath.parent / "epoch_metrics.json").write_text(json.dumps(self.history, indent=2))

        if logs is not None:
            logs["val_macro_f1"] = entry["val_macro_f1"]
        if entry["val_macro_f1"] > self.best:
            self.best = entry["val_macro_f1"]
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.model.save(self.filepath)
            if self.verbose:
                print(
                    f"  macro F1 {entry['val_macro_f1']:.4f} "
                    f"(top1 {entry['val_top1']:.4f}) -> saved {self.filepath.name}",
                    flush=True,
                )


def standard_callbacks(out_dir: str | Path, patience: int = 2) -> list:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return [
        tf.keras.callbacks.CSVLogger(str(out / "training_log.csv"), append=True),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=1, min_lr=1e-6, verbose=1
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=patience, restore_best_weights=True, verbose=1
        ),
    ]
