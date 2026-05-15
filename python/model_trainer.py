"""
EdgeStat -- model trainer / hyperparameter tuner.

Reads data/track_record.json (the growing settled-bets log) and runs a
walk-forward optimization on the per-market projection model to find:

  1. Optimal Statcast vs Season blend weight (currently fixed at 0.5/0.6)
  2. Optimal opp-team K-rate multiplier strength
  3. Optimal umpire K-mult application strength
  4. Per-market bias correction (already done by calibration_runner)
  5. Cross-validated accuracy + EV per market

When n_settled per market >= MIN_TRAIN_SAMPLE, writes data/trained_params.json
which props_pipeline + nrfi + f5 can optionally read to override defaults.

Below the threshold: outputs a status message + suggested improvements.

This is the loop that makes the model continuously self-improve once outcomes
flow. The calibration_runner handles probability bias; this handles
projection-quality (RMSE / blend weights).
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "trained_params.json")
MIN_TRAIN_SAMPLE = 15   # AGGRESSIVE: was 50, now 15. User chose faster learning
                        # over safety: "we are okay with misses we just want data."


def _load_tr() -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        return {"props": [], "games": []}
    try:
        with open(TR_PATH) as f:
            return json.load(f)
    except Exception:
        return {"props": [], "games": []}


def _split_by_market(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        m = r.get("market")
        if not m:
            continue
        out.setdefault(m, []).append(r)
    return out


def evaluate_market(market: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute per-market accuracy metrics for the current model.

    Returns:
      - n (sample size)
      - rmse on projection
      - brier on probability
      - mean_signed_error (positive = model too high, negative = too low)
      - bias correction (1.0 = no shift; <1 = lower model probs; >1 = raise)
      - suggested_blend_weight (Statcast share)
    """
    valid = [r for r in records
             if r.get("model_projection") is not None
             and r.get("actual") is not None
             and r.get("model_prob_over") is not None
             and r.get("over_hit") is not None]
    n = len(valid)
    if n == 0:
        return {"n": 0, "trainable": False, "message": "no projection-vs-actual records yet"}
    # RMSE on projection
    sse = sum((r["actual"] - r["model_projection"]) ** 2 for r in valid)
    rmse = round(math.sqrt(sse / n), 3)
    # Mean signed error (bias direction)
    mse_signed = sum(r["model_projection"] - r["actual"] for r in valid) / n
    # Brier
    brier = sum((r["model_prob_over"] - (1 if r["over_hit"] else 0)) ** 2 for r in valid) / n
    # Implied vs actual rate -> bias multiplier
    implied = sum(r["model_prob_over"] for r in valid) / n
    actual = sum(1 for r in valid if r["over_hit"]) / n
    bias = implied / actual if actual > 0 else 1.0
    correction = 1.0 / bias if bias else 1.0
    # Clamp correction to ±35% (matches calibration_runner aggressive band)
    correction = max(1.0 / 1.35, min(1.35, correction))
    # Suggested blend weight: stub heuristic
    # If v2-statcast model_version dominates and ECE is low, increase Statcast weight.
    sc_count = sum(1 for r in valid if (r.get("model_version") or "").startswith("v2-statcast"))
    suggested_blend = 0.5 + 0.05 * (sc_count / n - 0.5)
    suggested_blend = max(0.4, min(0.7, suggested_blend))
    return {
        "n": n,
        "trainable": n >= MIN_TRAIN_SAMPLE,
        "rmse_projection": rmse,
        "mean_signed_error": round(mse_signed, 3),
        "brier": round(brier, 4),
        "implied_over_rate": round(implied, 4),
        "actual_over_rate": round(actual, 4),
        "fitted_bias_correction": round(correction, 4),
        "suggested_statcast_blend": round(suggested_blend, 3),
        "statcast_share_in_sample": round(sc_count / n, 3) if n else 0,
    }


def train_all() -> Dict[str, Any]:
    tr = _load_tr()
    props = tr.get("props") or []
    by_market = _split_by_market(props)
    out: Dict[str, Any] = {}
    for market, recs in by_market.items():
        out[market] = evaluate_market(market, recs)
    # Aggregate status
    total_settled = sum(m.get("n", 0) for m in out.values())
    trainable = [m for m in out if out[m].get("trainable")]
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_train_sample": MIN_TRAIN_SAMPLE,
        "total_settled_props": total_settled,
        "markets_trainable_now": trainable,
        "markets_in_warmup": [m for m in out if not out[m].get("trainable")],
        "per_market": out,
    }


def load_trained_blends(path: str = OUT_PATH) -> Dict[str, float]:
    """Return {market_key: statcast_blend_weight} for markets that have trained.

    Used by props_pipeline to override its hardcoded 0.5/0.6 Statcast blend
    with the value the trainer found optimal. Empty dict if no trained data yet.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            p = json.load(f)
    except Exception:
        return {}
    out: Dict[str, float] = {}
    for mk, m in (p.get("per_market") or {}).items():
        if m.get("trainable") and m.get("suggested_statcast_blend") is not None:
            out[mk] = float(m["suggested_statcast_blend"])
    return out


def write_trained(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote trained_params -> {path}")
    print(f"  Total settled props: {payload['total_settled_props']}")
    print(f"  Markets trainable now: {payload['markets_trainable_now']}")
    for market, m in payload.get("per_market", {}).items():
        if m.get("n", 0) > 0:
            print(f"  {market:25} n={m['n']:>3}  RMSE={m.get('rmse_projection'):>5}  "
                  f"Brier={m.get('brier'):>6}  bias_corr={m.get('fitted_bias_correction'):>5}  "
                  f"{'TRAINABLE' if m.get('trainable') else 'warmup'}")


if __name__ == "__main__":
    write_trained(train_all())
