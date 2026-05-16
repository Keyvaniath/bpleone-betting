"""
EdgeStat -- per-market learning curves.

Visual proof the model is improving over time. For each market, slides a
7-day rolling window across track_record and computes Brier + hit rate at
each step. The /training page plots these as line charts so Brandon can
SEE the loop working (Brier shrinking, hit rate climbing).

Output: data/learning_curves.json
  {
    "generated_at": "...",
    "window_days": 7,
    "stride_days": 1,
    "by_market": {
      "batter_total_bases": {
        "labels": ["2026-05-01", "2026-05-02", ...],
        "brier":  [0.231, 0.227, 0.222, ...],
        "hit_rate": [0.534, 0.541, 0.548, ...],
        "n":       [820,   840,   855,   ...]
      },
      ...
    },
    "summary": {
      "best_market":  {"market": "...", "brier_delta": -0.04},
      "worst_market": {"market": "...", "brier_delta": +0.01}
    }
  }

Front-end: chart.js line chart on /training, one dataset per market,
toggleable via legend.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "learning_curves.json")

try:
    import config as _cfg
    WINDOW_DAYS = _cfg.get("learning_curves.window_days", 7)
    STRIDE_DAYS = _cfg.get("learning_curves.stride_days", 1)
    MIN_PER_WINDOW = _cfg.get("learning_curves.min_per_window", 20)
except Exception:
    WINDOW_DAYS = 7
    STRIDE_DAYS = 1
    MIN_PER_WINDOW = 20


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _date_of(r: Dict[str, Any]) -> Optional[dt.date]:
    s = r.get("date")
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def _window_stats(records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [r for r in records
             if r.get("model_prob_over") is not None and r.get("over_hit") is not None]
    if len(valid) < MIN_PER_WINDOW:
        return None
    brier_sum = 0.0
    hits = 0
    for r in valid:
        p = max(0.001, min(0.999, float(r["model_prob_over"])))
        y = 1 if r["over_hit"] else 0
        brier_sum += (p - y) ** 2
        side = "OVER" if p >= 0.5 else "UNDER"
        if (side == "OVER" and y == 1) or (side == "UNDER" and y == 0):
            hits += 1
    return {
        "brier": round(brier_sum / len(valid), 4),
        "hit_rate": round(hits / len(valid), 4),
        "n": len(valid),
    }


def curves_for_market(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {"labels": [], "brier": [], "hit_rate": [], "n": []}
    by_date: Dict[dt.date, List[Dict[str, Any]]] = {}
    for r in records:
        d = _date_of(r)
        if d:
            by_date.setdefault(d, []).append(r)
    if not by_date:
        return {"labels": [], "brier": [], "hit_rate": [], "n": []}
    sorted_dates = sorted(by_date.keys())
    labels: List[str] = []
    brier: List[Optional[float]] = []
    hit_rate: List[Optional[float]] = []
    n: List[int] = []
    for i in range(0, len(sorted_dates) - WINDOW_DAYS + 1, STRIDE_DAYS):
        window_dates = sorted_dates[i:i + WINDOW_DAYS]
        records_in_window: List[Dict[str, Any]] = []
        for d in window_dates:
            records_in_window.extend(by_date[d])
        stats = _window_stats(records_in_window)
        if not stats:
            continue
        labels.append(window_dates[-1].isoformat())
        brier.append(stats["brier"])
        hit_rate.append(stats["hit_rate"])
        n.append(stats["n"])
    return {"labels": labels, "brier": brier, "hit_rate": hit_rate, "n": n}


def run() -> Dict[str, Any]:
    tr = _load(TR_PATH)
    props = tr.get("props", []) or []
    by_market: Dict[str, List[Dict[str, Any]]] = {}
    for r in props:
        m = r.get("market")
        if m:
            by_market.setdefault(m, []).append(r)

    per_market: Dict[str, Dict[str, Any]] = {}
    deltas: List[Dict[str, Any]] = []
    for market, recs in by_market.items():
        curves = curves_for_market(recs)
        per_market[market] = curves
        b = curves["brier"]
        if len(b) >= 2:
            delta = round(b[-1] - b[0], 4)
            deltas.append({"market": market, "brier_delta": delta,
                           "first": b[0], "last": b[-1],
                           "n_windows": len(b)})

    deltas.sort(key=lambda d: d["brier_delta"])
    summary = {
        "best_market":  deltas[0]  if deltas else None,
        "worst_market": deltas[-1] if deltas else None,
        "all": deltas,
    }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "stride_days": STRIDE_DAYS,
        "min_per_window": MIN_PER_WINDOW,
        "by_market": per_market,
        "summary": summary,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Markets: {len(p['by_market'])}")
    if p["summary"]["best_market"]:
        b = p["summary"]["best_market"]
        print(f"  Best:  {b['market']} dBrier {b['brier_delta']:+.4f} "
              f"({b['first']:.4f} -> {b['last']:.4f}, {b['n_windows']} windows)")
    if p["summary"]["worst_market"]:
        w = p["summary"]["worst_market"]
        print(f"  Worst: {w['market']} dBrier {w['brier_delta']:+.4f} "
              f"({w['first']:.4f} -> {w['last']:.4f}, {w['n_windows']} windows)")
