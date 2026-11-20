"""Calibrated confidence for the shipped TFLite classifier.

The model outputs a softmax over 38 PlantVillage classes. Those numbers are
*relative* scores, not probabilities: a frozen-backbone transfer model is
usually over-confident, so a 0.70 does not mean "right 70% of the time". Farmer
photos make this worse, because they are out of the training distribution.

Temperature scaling fixes the numbers without changing a single prediction:
argmax is invariant, so accuracy stays exactly where it was. Only the
confidence becomes meaningful, which is what the abstention rules depend on.

The TFLite graph ends in softmax, so we recover its logits from the
probabilities (``log p`` differs from the true logits by one constant, which
cancels inside the softmax) and divide by the fitted temperature:

    q = softmax(log(p) / T)

T > 1 softens an over-confident model. This module is the single definition
used by the backend, the calibration script and the mobile app (which mirrors
``apply_temperature`` in Dart).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

DEFAULT_TEMPERATURE = 1.0
LOG_EPS = 1e-12


def apply_temperature(probs: np.ndarray, temperature: float) -> np.ndarray:
    """Return temperature-scaled probabilities for one or many rows.

    ``probs`` may be shape (n_classes,) or (n, n_classes). The argmax order of
    every row is preserved, so a calibrated model makes identical predictions.
    """
    p = np.asarray(probs, dtype=np.float64)
    if temperature is None or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError(f"invalid temperature: {temperature!r}")
    if temperature == 1.0:
        return p.astype(np.float32)

    single = p.ndim == 1
    rows = p.reshape(1, -1) if single else p
    # Probabilities can be exactly 0 after float16 export; clip so log is finite.
    logits = np.log(np.clip(rows, LOG_EPS, None)) / float(temperature)
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    scaled = exp / exp.sum(axis=1, keepdims=True)
    return (scaled[0] if single else scaled).astype(np.float32)


def fit_temperature(probs: np.ndarray, y_true: np.ndarray) -> float:
    """Fit T by minimising negative log-likelihood on held-out predictions."""
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(y_true, dtype=np.int64)
    log_p = np.log(np.clip(p, LOG_EPS, None))

    def nll(t: float) -> float:
        logits = log_p / t
        logits -= logits.max(axis=1, keepdims=True)
        log_z = np.log(np.exp(logits).sum(axis=1))
        log_prob_true = logits[np.arange(len(y)), y] - log_z
        return float(-log_prob_true.mean())

    # Coarse grid then a fine pass around the best point; no scipy needed.
    grid = np.arange(0.50, 5.001, 0.05)
    losses = [nll(t) for t in grid]
    best = float(grid[int(np.argmin(losses))])
    fine = np.arange(max(0.05, best - 0.10), best + 0.1001, 0.005)
    losses = [nll(t) for t in fine]
    return round(float(fine[int(np.argmin(losses))]), 3)


def expected_calibration_error(
    probs: np.ndarray, y_true: np.ndarray, bins: int = 15
) -> float:
    """Standard top-1 ECE: |accuracy - confidence| averaged over confidence bins."""
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == y_true).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi)
        if not mask.any():
            continue
        ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def _slice(probs: np.ndarray, y_true: np.ndarray, keys: Iterable[str], class_keys: list[str]):
    wanted = [class_keys.index(k) for k in keys if k in class_keys]
    if not wanted:
        return None, None
    mask = np.isin(y_true, wanted)
    return probs[mask], y_true[mask]


def select_thresholds(
    probs: np.ndarray,
    y_true: np.ndarray,
    class_keys: list[str],
    healthy_keys: list[str],
    target_precision: float = 0.90,
    min_coverage: float = 0.60,
) -> dict[str, Any]:
    """Pick an abstention threshold from measured precision/coverage.

    The rule the app needs: "when I do not say *unclear*, how often am I right?"
    We keep as many photos as possible while holding accepted-set precision at or
    above ``target_precision``: the answer is the *lowest* confidence threshold
    that still meets the target, because a lower threshold accepts more photos.

    Thresholds are scanned from low confidence upward so the chosen value is a
    measured operating point, not a guess. If nothing reaches the target the
    strictest measured point is kept and ``target_met = false`` is recorded
    rather than inventing a number.
    """
    conf = probs.max(axis=1)
    correct = probs.argmax(axis=1) == y_true

    candidates = np.unique(np.round(conf, 4))
    chosen: float | None = None
    best_precision, best_threshold = -1.0, float(candidates.min())
    for t in candidates:
        accepted = conf >= t
        coverage = float(accepted.mean())
        if coverage < min_coverage:
            break  # raising t further only shrinks coverage
        precision = float(correct[accepted].mean())
        if precision > best_precision:
            best_precision, best_threshold = precision, float(t)
        if precision >= target_precision:
            chosen = float(t)
            break

    target_met = chosen is not None
    threshold = chosen if chosen is not None else best_threshold
    accepted = conf >= threshold
    return {
        "threshold": round(threshold, 4),
        "target_precision": target_precision,
        "min_coverage": min_coverage,
        "target_met": bool(target_met),
        "measured_coverage": round(float(accepted.mean()), 4),
        "measured_precision": round(float(correct[accepted].mean()), 4),
        "measured_recall": round(float(correct[accepted].sum() / max(1, correct.sum())), 4),
    }


def select_healthy_threshold(
    probs: np.ndarray,
    y_true: np.ndarray,
    class_keys: list[str],
    healthy_keys: list[str],
    target_precision: float = 0.95,
    base_threshold: float = 0.55,
) -> dict[str, Any]:
    """Confidence needed before telling a farmer the leaf is healthy.

    A false "healthy" is the costliest mistake: it stops treatment. So the
    healthy verdict gets its own, stricter threshold, measured on the validation
    photos the model called healthy.
    """
    healthy_idx = [class_keys.index(k) for k in healthy_keys if k in class_keys]
    if not healthy_idx:
        return {"threshold": base_threshold, "target_met": False, "reason": "no healthy classes"}

    pred = probs.argmax(axis=1)
    claimed = np.isin(pred, healthy_idx)
    if claimed.sum() == 0:
        return {"threshold": base_threshold, "target_met": False, "reason": "model never predicts healthy"}

    conf = probs.max(axis=1)[claimed]
    truly_healthy = np.isin(y_true, healthy_idx)[claimed]

    # Same rule as the abstention threshold: lowest confidence that still keeps
    # healthy claims trustworthy, so the verdict stays usable.
    chosen: float | None = None
    best_precision, best_threshold = -1.0, float(conf.max())
    for t in np.unique(np.round(conf, 4)):
        accepted = conf >= t
        precision = float(truly_healthy[accepted].mean())
        if precision > best_precision:
            best_precision, best_threshold = precision, float(t)
        if precision >= target_precision:
            chosen = float(t)
            break

    met = chosen is not None
    threshold = chosen if chosen is not None else best_threshold
    # Below the abstention threshold the answer is "unclear" anyway.
    threshold = round(min(0.999, max(base_threshold, threshold)), 4)
    accepted = claimed & (probs.max(axis=1) >= threshold)
    return {
        "threshold": threshold,
        "target_precision": target_precision,
        "target_met": bool(met),
        "measured_coverage": round(float(accepted.sum() / max(1, claimed.sum())), 4),
        "measured_precision": round(
            float(np.isin(y_true, healthy_idx)[accepted].mean()), 4
        )
        if accepted.any()
        else None,
    }


def load_calibration(path: str | Path) -> dict[str, Any]:
    """Read a calibration file, falling back to a no-op if it is absent."""
    p = Path(path)
    if not p.exists():
        return {
            "temperature": DEFAULT_TEMPERATURE,
            "min_confidence": 0.55,
            "healthy_confidence": 0.60,
            "source": "defaults",
        }
    data = json.loads(p.read_text("utf-8"))
    data.setdefault("temperature", DEFAULT_TEMPERATURE)
    data.setdefault("min_confidence", 0.55)
    data.setdefault("healthy_confidence", 0.60)
    return data
