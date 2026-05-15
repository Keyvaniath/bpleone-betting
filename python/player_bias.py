"""
EdgeStat -- per-player bias overrides.

Market-level bias correction (in calibration_runner.py) handles the average
case but doesn't fix structural player-level errors. Tyler Glasnow's K props
are systematically under-projected; Andy Pages had a 3-HR game we couldn't
have foreseen. The anomaly detector flags these but only as warnings.

This module promotes the FLAGGED systematic anomalies (|z| >= 2,
n >= MIN_PLAYER_SAMPLE) into actual model_prob_over corrections that
props_pipeline applies to those specific (player_id, market) pairs.

Writes data/player_bias.json:
  {
    "generated_at": "...",
    "by_pid_market": {
      "543037_pitcher_strikeouts": {
        "player": "Tyler Glasnow",
        "n": 4,
        "z_score": -2.7,
        "mean_residual": -5.5,
        "boost_factor": 1.18,   # multiplicative on model_prob_over (capped)
        "direction": "boost",   # because model under-predicts him
        "note": "model UNDER-predicts by avg 5.50"
      }
    }
  }

props_pipeline reads this and multiplies p_over by boost_factor when both
player_id AND market match a flagged override. Applied AFTER market-level
calibration so it stacks.

Threshold: z >= 2.0 + n >= 3 (same as anomaly detector). Boost capped at
±20% (less aggressive than market-level because we have less data).
"""
from __future__ import annotations

import os
import json
import math
import statistics
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "player_bias.json")

MIN_PLAYER_N = 3
Z_THRESHOLD = 2.0
MAX_BOOST = 1.20      # cap +/- 20%
MIN_BOOST = 1.0 / 1.20


def run() -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "by_pid_market": {}}
        _write(payload)
        return payload
    with open(TR_PATH) as f:
        tr = json.load(f)
    props = tr.get("props", [])
    # Enrich with residual
    enriched = []
    for p in props:
        proj = p.get("model_projection")
        actual = p.get("actual")
        if proj is None or actual is None:
            continue
        enriched.append({**p, "residual": actual - proj})

    # Per-market residual std (used as the z-score denominator)
    by_market: Dict[str, List[float]] = {}
    for r in enriched:
        by_market.setdefault(r["market"], []).append(r["residual"])
    market_std: Dict[str, float] = {}
    for mk, vals in by_market.items():
        if len(vals) >= 2:
            market_std[mk] = statistics.pstdev(vals) or 1e-6

    # Group by (pid, market)
    by_pm: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in enriched:
        key = (r.get("player_id"), r.get("market"))
        if key[0] is None:
            continue
        by_pm.setdefault(key, []).append(r)

    out: Dict[str, Dict[str, Any]] = {}
    for (pid, market), rows in by_pm.items():
        if len(rows) < MIN_PLAYER_N:
            continue
        std = market_std.get(market)
        if not std:
            continue
        mean_r = sum(r["residual"] for r in rows) / len(rows)
        z = mean_r / std
        if abs(z) < Z_THRESHOLD:
            continue
        # Direction:
        #   residual > 0 means actual > projection -> model UNDER-predicts
        #     -> BOOST model_prob_over (multiplier > 1)
        #   residual < 0 means actual < projection -> model OVER-predicts
        #     -> SHRINK model_prob_over (multiplier < 1)
        # Magnitude: scale by |z|/4 so z=2 -> 12% adjustment, z=4 -> 25% (capped)
        raw_boost = 1.0 + (mean_r / std) * 0.06  # 6% per std away
        boost = max(MIN_BOOST, min(MAX_BOOST, raw_boost))
        out[f"{pid}_{market}"] = {
            "player": rows[0].get("player"),
            "player_id": pid,
            "market": market,
            "n": len(rows),
            "z_score": round(z, 2),
            "mean_residual": round(mean_r, 3),
            "boost_factor": round(boost, 4),
            "direction": "boost" if boost > 1 else "shrink",
            "note": (f"model UNDER-predicts by avg {mean_r:.2f} -- boost OVER probs {(boost-1)*100:+.1f}%"
                     if boost > 1 else
                     f"model OVER-predicts by avg {abs(mean_r):.2f} -- shrink OVER probs {(boost-1)*100:+.1f}%"),
        }
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_player_n": MIN_PLAYER_N,
        "z_threshold": Z_THRESHOLD,
        "max_boost": MAX_BOOST,
        "n_overrides": len(out),
        "by_pid_market": out,
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)


def load_overrides(path: str = OUT_PATH) -> Dict[str, float]:
    """Return {`{pid}_{market}`: boost_factor} -- props_pipeline calls this."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            p = json.load(f)
    except Exception:
        return {}
    out: Dict[str, float] = {}
    for key, v in (p.get("by_pid_market") or {}).items():
        bf = v.get("boost_factor")
        if bf is not None:
            out[key] = float(bf)
    return out


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_overrides']} per-player overrides")
    for k, v in list(p["by_pid_market"].items())[:10]:
        print(f"  {v['player']:25} {v['market']:25} n={v['n']:>2} z={v['z_score']:+.1f} "
              f"boost={v['boost_factor']:.3f} -- {v['note']}")
