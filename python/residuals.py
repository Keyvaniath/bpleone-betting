"""
EdgeStat -- residual analysis.

Sister to calibration_runner.py. Where calibration looks at "is the model
biased on average?" (single bias number per market), this looks at
WHERE the model is systematically wrong: by player, by market, by side,
and across the projection range.

Output: data/residuals.json
  {
    "generated_at": "...",
    "markets": {
      "batter_total_bases": {
        "n": 4,
        "mean_residual": -1.83,         # negative = model over-predicts on avg
        "median_residual": -1.93,
        "std_residual": 0.13,
        "mae": 1.83,                    # mean absolute error
        "rmse": 1.83,
        "histogram": [bin counts for visualization],
        "histogram_edges": [-3, -2.5, -2, ...],
        "by_projection_band": {         # "is the model worse in some range?"
          "0-1": {n: 1, mean_residual: -1.5},
          "1-2": {n: 3, mean_residual: -1.9},
        },
        "worst_misses": [               # top 5 by |residual|
          {player, line, projection, actual, residual, date}
        ]
      }
    },
    "player_systematic": [              # players with >=2 settled records
      {player, market, n, mean_residual, suggests: "shrink"|"boost"|"ok"}
    ]
  }

Visible at /residuals.html so we can see "model overestimates batter total
bases by ~1.8 -- needs a 30% downward adjustment" rather than a single
opaque "bias=5.18" number.
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
RES_PATH = os.path.join(DATA_DIR, "residuals.json")

LOOKBACK_DAYS = 30
MIN_PLAYER_N = 2     # min samples to flag a player-level systematic error
PROJ_BANDS = [(0, 0.5), (0.5, 1), (1, 1.5), (1.5, 2), (2, 3), (3, 5), (5, 10), (10, 99)]


def _within_window(date_str: str, today: dt.date, n_days: int) -> bool:
    try:
        return (today - dt.date.fromisoformat(date_str)).days <= n_days
    except Exception:
        return False


def _stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"n": 0}
    n = len(values)
    mean = sum(values) / n
    median = statistics.median(values)
    abs_vals = [abs(v) for v in values]
    mae = sum(abs_vals) / n
    rmse = math.sqrt(sum(v * v for v in values) / n)
    std = statistics.pstdev(values) if n > 1 else 0.0
    return {
        "n": n,
        "mean_residual": round(mean, 3),
        "median_residual": round(median, 3),
        "std_residual": round(std, 3),
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
    }


def _histogram(values: List[float], n_bins: int = 11) -> Dict[str, List[float]]:
    if not values:
        return {"edges": [], "counts": []}
    lo, hi = min(values), max(values)
    if lo == hi:
        lo -= 0.5
        hi += 0.5
    # Make symmetric around 0 if possible so over-predict vs under-predict is visually clear.
    span = max(abs(lo), abs(hi))
    lo, hi = -span, span
    step = (hi - lo) / n_bins
    edges = [round(lo + i * step, 3) for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for v in values:
        idx = min(n_bins - 1, max(0, int((v - lo) / step)))
        counts[idx] += 1
    return {"edges": edges, "counts": counts}


def _by_band(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in records:
        proj = r.get("model_projection")
        res = r.get("residual")
        if proj is None or res is None:
            continue
        for lo, hi in PROJ_BANDS:
            if lo <= proj < hi:
                k = f"{lo}-{hi}"
                out.setdefault(k, {"residuals": [], "n": 0})
                out[k]["residuals"].append(res)
                out[k]["n"] += 1
                break
    # Summarize each band
    for k, v in out.items():
        vals = v.pop("residuals")
        v["mean_residual"] = round(sum(vals) / len(vals), 3)
        v["mae"] = round(sum(abs(x) for x in vals) / len(vals), 3)
    return out


def _worst_misses(records: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    scored = [r for r in records if r.get("residual") is not None]
    scored.sort(key=lambda r: abs(r["residual"]), reverse=True)
    out = []
    for r in scored[:top_n]:
        out.append({
            "player": r.get("player"),
            "date": r.get("date"),
            "line": r.get("line"),
            "projection": r.get("model_projection"),
            "actual": r.get("actual"),
            "residual": r.get("residual"),
        })
    return out


def run(today: Optional[dt.date] = None) -> Dict[str, Any]:
    today = today or dt.date.today()
    if not os.path.exists(TR_PATH):
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "warning": "no track_record.json yet",
            "markets": {},
            "player_systematic": [],
        }
        _write(payload)
        return payload

    with open(TR_PATH) as f:
        tr = json.load(f)
    props = tr.get("props", [])

    # Pre-compute residual = actual - model_projection per record
    enriched: List[Dict[str, Any]] = []
    for p in props:
        if not _within_window(p.get("date", ""), today, LOOKBACK_DAYS):
            continue
        proj = p.get("model_projection")
        actual = p.get("actual")
        if proj is None or actual is None:
            continue
        enriched.append({**p, "residual": round(actual - proj, 3)})

    # Per-market analysis
    markets: Dict[str, Any] = {}
    for mk in sorted({r["market"] for r in enriched}):
        subset = [r for r in enriched if r["market"] == mk]
        vals = [r["residual"] for r in subset]
        stats = _stats(vals)
        stats["histogram"] = _histogram(vals)
        stats["by_projection_band"] = _by_band(subset)
        stats["worst_misses"] = _worst_misses(subset)
        # Direction summary in plain English
        if abs(stats.get("mean_residual", 0)) < 0.1:
            stats["direction"] = "balanced (model centered on actual)"
        elif stats["mean_residual"] < 0:
            stats["direction"] = f"model OVER-predicts by avg {-stats['mean_residual']} -> shrink projections"
        else:
            stats["direction"] = f"model UNDER-predicts by avg {stats['mean_residual']} -> boost projections"
        markets[mk] = stats

    # Per-player systematic patterns
    by_player: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in enriched:
        key = (r.get("player"), r.get("market"))
        by_player.setdefault(key, []).append(r)
    player_systematic: List[Dict[str, Any]] = []
    for (pl, mk), rows in by_player.items():
        if len(rows) < MIN_PLAYER_N:
            continue
        vals = [r["residual"] for r in rows]
        mean_r = sum(vals) / len(vals)
        suggest = "shrink" if mean_r < -0.5 else "boost" if mean_r > 0.5 else "ok"
        player_systematic.append({
            "player": pl,
            "market": mk,
            "n": len(rows),
            "mean_residual": round(mean_r, 3),
            "mae": round(sum(abs(v) for v in vals) / len(vals), 3),
            "suggests": suggest,
        })
    player_systematic.sort(key=lambda x: abs(x["mean_residual"]), reverse=True)

    # Per-park / per-handedness slicing for systematic bias detection.
    # We don't always have park/handedness on settled records, but where we
    # do, surface "park X over-predicts by Y" so adjustments can be targeted.
    park_residuals: Dict[str, Dict[str, Any]] = {}
    hand_residuals: Dict[str, Dict[str, Any]] = {}
    for r in enriched:
        park = (r.get("park") or r.get("venue") or "").strip()
        if park:
            key = park
            slot = park_residuals.setdefault(key, {"residuals": [], "by_market": {}})
            slot["residuals"].append(r["residual"])
            mk = r.get("market") or "?"
            slot["by_market"].setdefault(mk, []).append(r["residual"])
        # Handedness inferred via debug.batter_hand or debug.pitcher_hand if present
        dbg = r.get("debug") or {}
        hand = dbg.get("batter_hand") or dbg.get("pitcher_hand")
        if hand:
            slot = hand_residuals.setdefault(hand, {"residuals": [], "by_market": {}})
            slot["residuals"].append(r["residual"])
            mk = r.get("market") or "?"
            slot["by_market"].setdefault(mk, []).append(r["residual"])

    def _summarize(by_key: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        out = {}
        for k, v in by_key.items():
            vals = v["residuals"]
            if not vals:
                continue
            out[k] = {
                "n": len(vals),
                "mean_residual": round(sum(vals) / len(vals), 3),
                "mae": round(sum(abs(x) for x in vals) / len(vals), 3),
                "by_market": {mk: {
                    "n": len(mk_vals),
                    "mean": round(sum(mk_vals) / len(mk_vals), 3),
                } for mk, mk_vals in v["by_market"].items() if len(mk_vals) >= 5},
            }
        # Sort by |mean_residual| desc
        return dict(sorted(out.items(), key=lambda kv: abs(kv[1]["mean_residual"]), reverse=True))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "lookback_days": LOOKBACK_DAYS,
        "min_player_n": MIN_PLAYER_N,
        "markets": markets,
        "player_systematic": player_systematic[:50],
        "total_props_analyzed": len(enriched),
        "by_park": _summarize(park_residuals),
        "by_handedness": _summarize(hand_residuals),
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RES_PATH, "w") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    p = run()
    print(f"Wrote {RES_PATH}")
    print(f"  Total props analyzed: {p.get('total_props_analyzed', 0)}")
    print(f"  Markets: {len(p.get('markets', {}))}")
    for mk, s in p.get("markets", {}).items():
        print(f"    {mk}: n={s['n']} mean_residual={s['mean_residual']} mae={s['mae']}  -> {s['direction']}")
    print(f"  Player systematic patterns (>= {p.get('min_player_n', 2)} samples): {len(p.get('player_systematic', []))}")
