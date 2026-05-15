"""
EdgeStat -- performance trend over time.

For each historical day in track_record.json, compute that day's hit rate,
Brier score, MAE, and ROI. Plot these over time so we can SEE the model
getting better (or not) as calibration corrections accumulate.

Writes data/perf_trend.json:
  {
    "generated_at": "...",
    "by_date": [
      {"date": "2026-05-14", "n": 1872, "hit_rate": 0.43, "brier": 0.21,
       "mae_residual": 1.5, "roi": -12.3, "data_weight_avg": 0.99}
    ],
    "trends": {
      "hit_rate_slope": -0.001,   # is hit rate trending up over time?
      "brier_slope": -0.002,      # is Brier getting smaller (better)?
      "mae_slope": -0.05          # is MAE shrinking (sharper)?
    }
  }
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
PERF_PATH = os.path.join(DATA_DIR, "perf_trend.json")


def _linreg_slope(xs: List[float], ys: List[float]) -> Optional[float]:
    """Ordinary least squares slope; None if degenerate."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return num / den


def _day_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {"n": 0}
    n = len(records)
    # Hit rate (of model's directional pick)
    hits = sum(1 for r in records if r.get("play_hit") is True)
    losses = sum(1 for r in records if r.get("play_hit") is False)
    graded = hits + losses
    hit_rate = hits / graded if graded > 0 else None

    # Brier on model_prob_over vs over_hit
    brier_terms = []
    abs_residuals = []
    for r in records:
        p = r.get("model_prob_over")
        if p is None:
            continue
        y = 1 if r.get("over_hit") else 0
        brier_terms.append((p - y) ** 2)
        proj = r.get("model_projection")
        actual = r.get("actual")
        if isinstance(proj, (int, float)) and isinstance(actual, (int, float)):
            abs_residuals.append(abs(actual - proj))
    brier = sum(brier_terms) / len(brier_terms) if brier_terms else None
    mae = sum(abs_residuals) / len(abs_residuals) if abs_residuals else None

    # ROI (1u flat) on records with real prices
    roi_stake = 0.0
    roi_pl = 0.0
    for r in records:
        if r.get("dk_over") is None and r.get("dk_under") is None:
            continue
        if r.get("play") not in ("OVER", "UNDER"):
            continue
        if r.get("play_hit") is None:
            continue
        roi_stake += 1.0
        if r.get("play_hit"):
            price = r.get("dk_over" if r["play"] == "OVER" else "dk_under")
            if price is None:
                roi_stake -= 1.0
                continue
            roi_pl += (price / 100.0) if price >= 0 else (100.0 / -price)
        else:
            roi_pl -= 1.0
    roi_pct = (roi_pl / roi_stake * 100.0) if roi_stake > 0 else None

    return {
        "n": n,
        "graded": graded,
        "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
        "brier": round(brier, 4) if brier is not None else None,
        "mae_residual": round(mae, 3) if mae is not None else None,
        "roi_pct": round(roi_pct, 2) if roi_pct is not None else None,
        "stake_records": int(roi_stake),
    }


def run() -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "by_date": [], "trends": {}}
        _write(payload)
        return payload
    with open(TR_PATH) as f:
        tr = json.load(f)
    props = tr.get("props", [])

    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for r in props:
        d = r.get("date")
        if not d:
            continue
        by_date.setdefault(d, []).append(r)

    per_day: List[Dict[str, Any]] = []
    for date in sorted(by_date.keys()):
        stats = _day_stats(by_date[date])
        stats["date"] = date
        per_day.append(stats)

    # Linear trends on dates with enough samples
    eligible = [d for d in per_day if d.get("graded", 0) >= 10]
    trends: Dict[str, Optional[float]] = {}
    if len(eligible) >= 2:
        xs = list(range(len(eligible)))
        trends["hit_rate_slope"] = _linreg_slope(xs, [d["hit_rate"] for d in eligible if d.get("hit_rate") is not None])
        trends["brier_slope"]    = _linreg_slope(xs, [d["brier"]    for d in eligible if d.get("brier") is not None])
        trends["mae_slope"]      = _linreg_slope(xs, [d["mae_residual"] for d in eligible if d.get("mae_residual") is not None])
        trends["days_used"] = len(eligible)
    else:
        trends["note"] = f"Need >=2 days with >=10 graded plays each; have {len(eligible)}"

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "by_date": per_day,
        "trends": trends,
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PERF_PATH, "w") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    p = run()
    print(f"Wrote {PERF_PATH}")
    print(f"  Days analyzed: {len(p['by_date'])}")
    for d in p["by_date"]:
        print(f"    {d['date']}: n={d['n']:>4} graded={d.get('graded',0):>4} "
              f"hit={d.get('hit_rate')} brier={d.get('brier')} MAE={d.get('mae_residual')} ROI={d.get('roi_pct')}")
    t = p.get("trends", {})
    if t.get("days_used"):
        print(f"  Trends over {t['days_used']} days:")
        print(f"    hit_rate slope: {t.get('hit_rate_slope')}")
        print(f"    brier slope: {t.get('brier_slope')} (negative = model getting better)")
        print(f"    MAE slope: {t.get('mae_slope')} (negative = sharper projections)")
    else:
        print(f"  {t.get('note')}")
