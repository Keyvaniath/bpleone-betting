"""
EdgeStat -- anomaly detector.

Walks track_record.json and flags player/market pairs whose residuals are
WAY outside the per-market norm. These are the "model is structurally
wrong on this player" cases that bias correction alone can't fix --
they need either a feature added or that player explicitly excluded.

Two kinds of anomalies:
  1. systematic: player has >= MIN_PLAYER_SAMPLE settled records on a
     market AND mean residual > 2x the market's std_residual
  2. outlier_day: single-day residual whose absolute value > 3x the
     market's std_residual (a player had a freak game we couldn't have
     foreseen -- worth knowing for the worst-misses gallery)

Writes data/anomalies.json:
  {
    "systematic": [
      {player, market, n, mean_residual, market_std, z_score, suggests}
    ],
    "outlier_days": [
      {player, market, date, residual, market_std, z_score, projection, actual}
    ]
  }
"""
from __future__ import annotations

import os
import json
import math
import statistics
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "anomalies.json")

try:
    import config as _cfg
    MIN_PLAYER_SAMPLE = _cfg.get("player_bias.min_player_n")
    SYSTEMATIC_Z_THRESHOLD = _cfg.get("anomalies.systematic_z_threshold")
    OUTLIER_Z_THRESHOLD = _cfg.get("anomalies.outlier_z_threshold")
except Exception:
    MIN_PLAYER_SAMPLE = 3
    SYSTEMATIC_Z_THRESHOLD = 2.0
    OUTLIER_Z_THRESHOLD = 3.0


def run() -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "systematic": [], "outlier_days": []}
        _write(payload)
        return payload

    with open(TR_PATH) as f:
        tr = json.load(f)
    props = tr.get("props", [])

    # Per-market residual distribution
    market_residuals: Dict[str, List[float]] = {}
    enriched: List[Dict[str, Any]] = []
    for p in props:
        proj = p.get("model_projection")
        actual = p.get("actual")
        if proj is None or actual is None:
            continue
        r = actual - proj
        market_residuals.setdefault(p["market"], []).append(r)
        enriched.append({**p, "residual": r})

    market_stats: Dict[str, Dict[str, float]] = {}
    for mk, vals in market_residuals.items():
        if len(vals) < 2:
            continue
        market_stats[mk] = {
            "mean": sum(vals) / len(vals),
            "std": statistics.pstdev(vals) or 1e-6,
            "n": len(vals),
        }

    # Group enriched by (player, market)
    by_pm: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in enriched:
        key = (r.get("player"), r.get("market"))
        by_pm.setdefault(key, []).append(r)

    systematic: List[Dict[str, Any]] = []
    for (player, market), rows in by_pm.items():
        if len(rows) < MIN_PLAYER_SAMPLE:
            continue
        ms = market_stats.get(market)
        if not ms:
            continue
        player_mean = sum(r["residual"] for r in rows) / len(rows)
        # Z-score relative to the market's residual distribution
        z = (player_mean - ms["mean"]) / ms["std"]
        if abs(z) < SYSTEMATIC_Z_THRESHOLD:
            continue
        systematic.append({
            "player": player,
            "market": market,
            "n": len(rows),
            "mean_residual": round(player_mean, 3),
            "market_mean": round(ms["mean"], 3),
            "market_std": round(ms["std"], 3),
            "z_score": round(z, 2),
            # residual = actual - projection. If residual > 0, actual > projection,
            # i.e., model is UNDER-estimating this player. If residual < 0, model
            # is OVER-estimating.
            "suggests": (f"model UNDER-predicts {player} by ~{player_mean:.2f}; "
                          f"player is sharper than the model thinks") if player_mean > 0
                         else (f"model OVER-predicts {player} by ~{abs(player_mean):.2f}; "
                                f"player is softer than the model thinks"),
        })
    systematic.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    # Outlier days (extreme single residuals)
    outliers: List[Dict[str, Any]] = []
    for r in enriched:
        ms = market_stats.get(r["market"])
        if not ms:
            continue
        z = (r["residual"] - ms["mean"]) / ms["std"]
        if abs(z) < OUTLIER_Z_THRESHOLD:
            continue
        outliers.append({
            "player": r.get("player"),
            "market": r.get("market"),
            "date": r.get("date"),
            "line": r.get("line"),
            "projection": r.get("model_projection"),
            "actual": r.get("actual"),
            "residual": round(r["residual"], 3),
            "market_std": round(ms["std"], 3),
            "z_score": round(z, 2),
        })
    outliers.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_player_sample": MIN_PLAYER_SAMPLE,
        "systematic_z_threshold": SYSTEMATIC_Z_THRESHOLD,
        "outlier_z_threshold": OUTLIER_Z_THRESHOLD,
        "n_systematic": len(systematic),
        "n_outliers": len(outliers),
        "systematic": systematic[:100],
        "outlier_days": outliers[:50],
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Systematic anomalies (player+market, |z| >= {SYSTEMATIC_Z_THRESHOLD}): {p['n_systematic']}")
    print(f"  Outlier days (single play, |z| >= {OUTLIER_Z_THRESHOLD}): {p['n_outliers']}")
    print()
    print("Top 10 systematic:")
    for a in p["systematic"][:10]:
        print(f"  {a['player']:30} {a['market']:25} n={a['n']:>2} z={a['z_score']:+.1f}  -> {a['suggests'][:60]}")
    print()
    print("Top 5 outlier days:")
    for a in p["outlier_days"][:5]:
        print(f"  {a['date']}  {a['player']:25} {a['market']:25} proj={a['projection']} actual={a['actual']} z={a['z_score']:+.1f}")
