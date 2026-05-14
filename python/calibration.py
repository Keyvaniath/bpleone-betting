"""
EdgeStat - Model calibration & reliability.

A model can have great accuracy and still be miscalibrated.  Miscalibration
means: when the model says "65%", maybe only 55% of those games actually win.
For a betting model, this is fatal — you'll bet at +EV that isn't really there.

This module measures and (optionally) fixes calibration:

  • Brier score  — overall calibration loss
  • Log loss / BCE — strictly proper scoring rule
  • Expected Calibration Error (ECE) — average gap between predicted prob
    and observed frequency, bucketed
  • Reliability diagram — bucketed predicted vs. observed
  • Platt scaling — fit a logistic regression to recalibrate

Run this against the ensemble's predictions to confirm we're not bluffing.
"""
from __future__ import annotations

import math
import json
import os
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple


# --------------------------- Scoring rules ---------------------------

def brier_score(preds: List[float], y: List[int]) -> float:
    """Mean (pred - actual)^2.  Lower is better.  Range [0, 1]."""
    return sum((p - yi) ** 2 for p, yi in zip(preds, y)) / len(preds)


def log_loss(preds: List[float], y: List[int]) -> float:
    """Binary cross entropy / log loss."""
    total = 0.0
    for p, yi in zip(preds, y):
        p = max(1e-7, min(1 - 1e-7, p))
        total += -(yi * math.log(p) + (1 - yi) * math.log(1 - p))
    return total / len(preds)


def accuracy(preds: List[float], y: List[int]) -> float:
    return sum(1 for p, yi in zip(preds, y) if (p >= 0.5) == (yi == 1)) / len(preds)


# --------------------------- Reliability / ECE ---------------------------

@dataclass
class ReliabilityBucket:
    bucket_low: float
    bucket_high: float
    n: int
    mean_predicted: float
    observed_frequency: float


def reliability_diagram(preds: List[float], y: List[int],
                        n_buckets: int = 10) -> List[ReliabilityBucket]:
    """Bucket predictions into n equal-width buckets [0,0.1), [0.1,0.2), ...
    and compute observed win rate in each."""
    buckets = []
    for b in range(n_buckets):
        lo = b / n_buckets
        hi = (b + 1) / n_buckets
        in_bucket = [(p, yi) for p, yi in zip(preds, y) if lo <= p < hi or (b == n_buckets - 1 and p == hi)]
        if not in_bucket:
            buckets.append(ReliabilityBucket(lo, hi, 0, (lo + hi) / 2, 0.0))
            continue
        mean_p = sum(p for p, _ in in_bucket) / len(in_bucket)
        obs = sum(yi for _, yi in in_bucket) / len(in_bucket)
        buckets.append(ReliabilityBucket(lo, hi, len(in_bucket), mean_p, obs))
    return buckets


def expected_calibration_error(preds: List[float], y: List[int],
                               n_buckets: int = 10) -> float:
    """Mean |predicted - observed| weighted by bucket size."""
    buckets = reliability_diagram(preds, y, n_buckets)
    n = len(preds)
    ece = 0.0
    for b in buckets:
        if b.n > 0:
            ece += (b.n / n) * abs(b.mean_predicted - b.observed_frequency)
    return ece


# --------------------------- Platt scaling ---------------------------

def platt_scale_fit(preds: List[float], y: List[int],
                    lr: float = 0.05, epochs: int = 200) -> Tuple[float, float]:
    """Fit a logistic: q = sigmoid(A * p + B) that recalibrates predictions."""
    A, B = 1.0, 0.0
    n = len(preds)
    for _ in range(epochs):
        gA = gB = 0.0
        for p, yi in zip(preds, y):
            z = A * p + B
            q = 1 / (1 + math.exp(-max(-30, min(30, z))))
            err = q - yi
            gA += err * p
            gB += err
        A -= lr * gA / n
        B -= lr * gB / n
    return A, B


def platt_scale_apply(preds: List[float], A: float, B: float) -> List[float]:
    """Apply learned Platt scaling to a list of predictions."""
    out = []
    for p in preds:
        z = A * p + B
        out.append(1 / (1 + math.exp(-max(-30, min(30, z)))))
    return out


# --------------------------- Full calibration report ---------------------------

def calibration_report(preds: List[float], y: List[int]) -> Dict:
    base = {
        "n":          len(preds),
        "brier":      round(brier_score(preds, y), 5),
        "log_loss":   round(log_loss(preds, y), 5),
        "accuracy":   round(accuracy(preds, y), 4),
        "ece":        round(expected_calibration_error(preds, y, n_buckets=10), 5),
    }
    diagram = reliability_diagram(preds, y, n_buckets=10)
    base["reliability"] = [{
        "bucket":     f"{b.bucket_low:.1f}-{b.bucket_high:.1f}",
        "n":          b.n,
        "predicted":  round(b.mean_predicted, 3),
        "observed":   round(b.observed_frequency, 3),
        "gap":        round(b.mean_predicted - b.observed_frequency, 3),
    } for b in diagram]
    # Compute Platt-scaled metrics for comparison.
    A, B = platt_scale_fit(preds, y)
    scaled = platt_scale_apply(preds, A, B)
    base["platt"] = {
        "A": round(A, 4), "B": round(B, 4),
        "brier_after":    round(brier_score(scaled, y), 5),
        "log_loss_after": round(log_loss(scaled, y), 5),
        "ece_after":      round(expected_calibration_error(scaled, y), 5),
    }
    return base


# --------------------------- Demo ---------------------------

def _synth_predictions_and_outcomes(n: int = 2000, seed: int = 7
                                    ) -> Tuple[List[float], List[int]]:
    """Generate a slightly miscalibrated prediction set + ground truth."""
    rng = random.Random(seed)
    preds = []
    outcomes = []
    for _ in range(n):
        true_p = max(0.05, min(0.95, rng.gauss(0.55, 0.13)))
        # Model is slightly overconfident: pushes probs toward 0/1.
        pred = max(0.02, min(0.98, true_p + (true_p - 0.5) * 0.20 + rng.gauss(0, 0.04)))
        preds.append(pred)
        outcomes.append(1 if rng.random() < true_p else 0)
    return preds, outcomes


if __name__ == "__main__":
    print("Generating 2,000 synthetic predictions (with small overconfidence bias)…")
    preds, y = _synth_predictions_and_outcomes(2000, seed=11)
    report = calibration_report(preds, y)
    print("\n=== Pre-calibration ===")
    print(f"  Brier      : {report['brier']:.5f}")
    print(f"  Log loss   : {report['log_loss']:.5f}")
    print(f"  Accuracy   : {report['accuracy']:.4f}")
    print(f"  ECE        : {report['ece']:.5f}")
    print("\n=== Reliability diagram (predicted vs observed) ===")
    for b in report["reliability"]:
        bar = "█" * int(b["n"] / 20)
        print(f"  {b['bucket']}: pred={b['predicted']:.3f}  obs={b['observed']:.3f}  "
              f"gap={b['gap']:+.3f}  n={b['n']:4d}  {bar}")
    print("\n=== Platt-scaled (after calibration) ===")
    print(f"  A = {report['platt']['A']}  B = {report['platt']['B']}")
    print(f"  Brier (after)    : {report['platt']['brier_after']:.5f}")
    print(f"  Log loss (after) : {report['platt']['log_loss_after']:.5f}")
    print(f"  ECE (after)      : {report['platt']['ece_after']:.5f}")

    os.makedirs("../data", exist_ok=True)
    with open("../data/calibration.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nWrote ../data/calibration.json")
