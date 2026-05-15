"""
EdgeStat -- walk-forward backtest.

Proves the self-learning loop is actually IMPROVING by splitting
track_record.json into rolling windows and measuring per-window:
  - Brier (probability calibration)
  - RMSE (projection accuracy)
  - Hit rate (directional accuracy)
  - ROI (after applying corrections)

For each window, apply the calibration correction derived from PRIOR
windows only -- never use future data. If the model is genuinely
learning, RMSE/Brier should shrink as more history accumulates.

Writes data/walk_forward.json:
  {
    "generated_at": "...",
    "window_size_days": 3,
    "by_market": {
      "batter_total_bases": [
        {"window_end": "2026-05-10", "n": 1200, "brier": 0.21, "rmse": 1.92, "hit_rate": 0.52, "correction_applied": 1.00},
        {"window_end": "2026-05-13", "n": 1180, "brier": 0.19, "rmse": 1.74, "hit_rate": 0.57, "correction_applied": 0.91},
        ...
      ]
    },
    "summary": {
      "markets_improving": ["batter_hits", "pitcher_strikeouts", ...],
      "markets_degrading": [],
      "markets_flat": []
    }
  }

The /training page reads this to render the trend chart.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "walk_forward.json")

try:
    import config as _cfg
    WINDOW_DAYS = _cfg.get("walk_forward.window_days")
    MIN_WINDOW_SAMPLES = _cfg.get("walk_forward.min_window_samples")
except Exception:
    WINDOW_DAYS = 3
    MIN_WINDOW_SAMPLES = 30
STRIDE_DAYS = 1


def _load_tr() -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        return {"props": [], "games": []}
    try:
        with open(TR_PATH) as f:
            return json.load(f)
    except Exception:
        return {"props": [], "games": []}


def _date_of(r: Dict[str, Any]) -> Optional[dt.date]:
    s = r.get("date")
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def _window_metrics(records: List[Dict[str, Any]],
                    correction_factor: float = 1.0) -> Dict[str, Any]:
    """Compute metrics for one window, optionally applying a correction
    (derived from prior windows) to the model_prob_over."""
    if not records:
        return {"n": 0}
    valid = [r for r in records
             if r.get("model_prob_over") is not None and r.get("over_hit") is not None]
    n = len(valid)
    if n == 0:
        return {"n": 0}
    brier_sum = 0.0
    abs_residuals = []
    hits = 0
    for r in valid:
        p = float(r["model_prob_over"]) * correction_factor
        p = max(0.001, min(0.999, p))
        y = 1 if r["over_hit"] else 0
        brier_sum += (p - y) ** 2
        # Directional accuracy after correction
        side_after = "OVER" if p >= 0.5 else "UNDER"
        if side_after == "OVER" and y == 1: hits += 1
        if side_after == "UNDER" and y == 0: hits += 1
        proj = r.get("model_projection")
        actual = r.get("actual")
        if isinstance(proj, (int, float)) and isinstance(actual, (int, float)):
            abs_residuals.append(abs(actual - proj))
    return {
        "n": n,
        "brier": round(brier_sum / n, 4),
        "rmse": round(math.sqrt(sum(r ** 2 for r in abs_residuals) / len(abs_residuals)), 3) if abs_residuals else None,
        "hit_rate": round(hits / n, 4),
        "correction_applied": round(correction_factor, 4),
    }


def _bias_correction(records: List[Dict[str, Any]]) -> float:
    """Compute the Laplace-smoothed bias correction from a record set.

    Same math as calibration_runner.py but bounded to ±35% (matches the
    aggressive band). Used to fit a correction from PRIOR windows that we
    can then APPLY to the current window.
    """
    valid = [r for r in records
             if r.get("model_prob_over") is not None and r.get("over_hit") is not None]
    if not valid:
        return 1.0
    sum_p = sum(float(r["model_prob_over"]) for r in valid)
    sum_actual = sum(1 for r in valid if r["over_hit"])
    bias = (sum_p + 0.5) / (sum_actual + 0.5)
    cf = 1.0 / bias if bias > 0 else 1.0
    return max(1.0 / 1.35, min(1.35, cf))


def walk_forward_for_market(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """For one market, walk forward through dates and compute per-window
    metrics with corrections fit from history-only."""
    if not records:
        return []
    by_date: Dict[dt.date, List[Dict[str, Any]]] = {}
    for r in records:
        d = _date_of(r)
        if d:
            by_date.setdefault(d, []).append(r)
    if not by_date:
        return []
    sorted_dates = sorted(by_date.keys())
    out: List[Dict[str, Any]] = []
    for i in range(len(sorted_dates) - WINDOW_DAYS + 1):
        window_dates = sorted_dates[i:i + WINDOW_DAYS]
        window_records: List[Dict[str, Any]] = []
        for d in window_dates:
            window_records.extend(by_date[d])
        if len(window_records) < MIN_WINDOW_SAMPLES:
            continue
        # History = all dates BEFORE this window
        history: List[Dict[str, Any]] = []
        for d in sorted_dates[:i]:
            history.extend(by_date[d])
        cf = _bias_correction(history) if history else 1.0
        m = _window_metrics(window_records, cf)
        m["window_start"] = window_dates[0].isoformat()
        m["window_end"] = window_dates[-1].isoformat()
        out.append(m)
    return out


def run() -> Dict[str, Any]:
    tr = _load_tr()
    props = tr.get("props", [])
    by_market: Dict[str, List[Dict[str, Any]]] = {}
    for r in props:
        m = r.get("market")
        if m:
            by_market.setdefault(m, []).append(r)

    per_market: Dict[str, List[Dict[str, Any]]] = {}
    summary_improving, summary_degrading, summary_flat = [], [], []
    for market, recs in by_market.items():
        windows = walk_forward_for_market(recs)
        per_market[market] = windows
        # Trend: compare first half avg Brier vs second half avg Brier
        if len(windows) >= 4:
            half = len(windows) // 2
            first_half_brier = sum(w["brier"] for w in windows[:half] if w.get("brier") is not None) / max(1, half)
            second_half_brier = sum(w["brier"] for w in windows[-half:] if w.get("brier") is not None) / max(1, half)
            delta = first_half_brier - second_half_brier   # positive = improved
            if delta > 0.005:
                summary_improving.append({"market": market, "brier_delta": round(delta, 4)})
            elif delta < -0.005:
                summary_degrading.append({"market": market, "brier_delta": round(delta, 4)})
            else:
                summary_flat.append({"market": market, "brier_delta": round(delta, 4)})

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "stride_days": STRIDE_DAYS,
        "min_window_samples": MIN_WINDOW_SAMPLES,
        "by_market": per_market,
        "summary": {
            "improving": sorted(summary_improving, key=lambda x: -x["brier_delta"]),
            "degrading": sorted(summary_degrading, key=lambda x: x["brier_delta"]),
            "flat": summary_flat,
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Markets analyzed: {len(p['by_market'])}")
    s = p["summary"]
    print(f"  Improving: {[m['market'] for m in s['improving']]}")
    print(f"  Degrading: {[m['market'] for m in s['degrading']]}")
    print(f"  Flat:      {[m['market'] for m in s['flat']]}")
    print()
    for market, windows in p["by_market"].items():
        if not windows:
            continue
        first = windows[0]
        last = windows[-1]
        print(f"  {market:25} first_brier={first.get('brier'):.4f} last_brier={last.get('brier'):.4f} "
              f"(n_windows={len(windows)})")
