"""
EdgeStat -- context-conditional bias detection.

Bulk market-level calibration washes out HIDDEN biases that depend on
context. The model might be:
  - Well-calibrated on day games but biased high on night games
  - Fine vs R-hand pitchers but systematically off vs L-hand pitchers
  - Calibrated outdoors but wrong indoors (dome physics differ)
  - Fine in normal weather but biased in wind-out conditions

This module slices track_record by context tags and flags any slice with
significant residual bias (n>=80, |bias|>=0.04). These slices need their
own correction factor on top of the market-level bias.

Slicing dimensions:
  - is_night_game: starts after 5pm local (rough heuristic from time field)
  - opp_pitcher_throws: L or R (from props record)
  - park_is_indoor: dome / retractable closed (from props record park field)
  - venue: home vs away (from is_home field)

Output: data/context_calibration.json
  {
    "generated_at": "...",
    "slices": [
      {
        "market": "batter_total_bases",
        "dim": "park_is_indoor",
        "slice_value": true,
        "n": 240,
        "bias": 1.07,                        # implied/actual rate ratio
        "correction_factor": 0.93,           # 1/bias, capped
        "mean_residual": 0.18,
        "z_score": 2.4,
        "note": "indoor games over-projecting TB by ~7%"
      }
    ],
    "n_significant": 3
  }

props_pipeline can apply these as a third-tier multiplier (market bias
* per-player bias * context bias) for projections that match the slice.
For now, surface them on /training so the operator sees what slices need
attention.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "context_calibration.json")

try:
    import config as _cfg
    MIN_SLICE_N = _cfg.get("context_calibration.min_slice_n", 80)
    BIAS_THRESHOLD = _cfg.get("context_calibration.bias_threshold", 0.04)
    Z_THRESHOLD = _cfg.get("context_calibration.z_threshold", 1.5)
    MAX_CORRECTION = _cfg.get("context_calibration.max_correction", 1.20)
except Exception:
    MIN_SLICE_N = 80
    BIAS_THRESHOLD = 0.04
    Z_THRESHOLD = 1.5
    MAX_CORRECTION = 1.20


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _is_night(r: Dict[str, Any]) -> Optional[bool]:
    """True if start time after 17:00 local. None if unknown."""
    t = r.get("game_time") or r.get("start_time") or r.get("time")
    if not t or not isinstance(t, str):
        return None
    # Accept "7:05pm", "19:05", "7:05 PM ET"
    s = t.strip().lower()
    try:
        if "pm" in s or "am" in s:
            hour_part = s.split(":")[0]
            hour = int(hour_part)
            if "pm" in s and hour != 12:
                hour += 12
            if "am" in s and hour == 12:
                hour = 0
            return hour >= 17
        if ":" in s:
            hour = int(s.split(":")[0])
            return hour >= 17
    except Exception:
        return None
    return None


def _park_indoor(r: Dict[str, Any]) -> Optional[bool]:
    """Best-effort: read from is_indoor flag or known indoor parks. Return
    None when no park info is available (don't default to outdoor since that
    would lump every untagged record into one fake slice)."""
    flag = r.get("park_is_indoor")
    if flag is not None:
        return bool(flag)
    park = (r.get("park") or "").lower()
    if not park:
        return None
    INDOOR = {"tropicana field", "rogers centre", "minute maid park",
              "globe life field", "chase field", "loandepot park",
              "t-mobile park", "american family field"}
    if any(name in park for name in INDOOR):
        return True
    OUTDOOR_KNOWN = {"fenway", "wrigley", "yankee stadium", "dodger stadium",
                     "oracle park", "citi field", "citizens bank", "petco park",
                     "great american", "kauffman", "comerica", "progressive field",
                     "guaranteed rate", "target field", "truist park", "busch stadium",
                     "pnc park", "nationals park", "oriole park", "angel stadium",
                     "coors field", "oakland coliseum"}
    if any(name in park for name in OUTDOOR_KNOWN):
        return False
    return None  # unknown park -> don't slice


def _pitcher_throws(r: Dict[str, Any]) -> Optional[str]:
    v = r.get("opp_pitcher_throws") or r.get("pitcher_throws")
    if v in ("L", "R"):
        return v
    return None


def _is_home(r: Dict[str, Any]) -> Optional[bool]:
    v = r.get("is_home")
    if isinstance(v, bool):
        return v
    return None


SLICERS: List[Tuple[str, Any]] = [
    ("park_is_indoor", _park_indoor),
    ("opp_pitcher_throws", _pitcher_throws),
    ("is_night_game", _is_night),
    ("is_home", _is_home),
]


def _slice_metrics(records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [r for r in records
             if r.get("model_prob_over") is not None and r.get("over_hit") is not None]
    n = len(valid)
    if n < MIN_SLICE_N:
        return None
    sum_p = sum(float(r["model_prob_over"]) for r in valid)
    sum_actual = sum(1 for r in valid if r["over_hit"])
    # Laplace-smoothed bias
    bias_raw = (sum_p + 0.5) / (sum_actual + 0.5)
    cf_raw = 1.0 / bias_raw if bias_raw > 0 else 1.0
    cf = max(1.0 / MAX_CORRECTION, min(MAX_CORRECTION, cf_raw))
    implied_rate = sum_p / n
    actual_rate = sum_actual / n
    # z-score on residual using binomial std (sqrt(p(1-p)/n)) under null = no bias
    std = math.sqrt(max(1e-9, implied_rate * (1 - implied_rate) / n))
    z = (implied_rate - actual_rate) / std if std > 0 else 0
    return {
        "n": n,
        "implied_rate": round(implied_rate, 4),
        "actual_rate": round(actual_rate, 4),
        "bias": round(bias_raw, 4),
        "correction_factor": round(cf, 4),
        "mean_residual": round(implied_rate - actual_rate, 4),
        "z_score": round(z, 2),
    }


def run() -> Dict[str, Any]:
    tr = _load(TR_PATH)
    props = tr.get("props", []) or []

    # First pass: compute market-level baseline residual so we can report
    # the EXTRA bias attributable to each context slice (not the bulk bias
    # that market-level calibration already catches).
    market_baseline: Dict[str, Dict[str, float]] = {}
    by_market: Dict[str, List[Dict[str, Any]]] = {}
    for r in props:
        m = r.get("market")
        if not m:
            continue
        if r.get("model_prob_over") is None or r.get("over_hit") is None:
            continue
        by_market.setdefault(m, []).append(r)
    for m, recs in by_market.items():
        n = len(recs)
        if n == 0:
            continue
        sum_p = sum(float(r["model_prob_over"]) for r in recs)
        sum_a = sum(1 for r in recs if r["over_hit"])
        market_baseline[m] = {
            "implied_rate": sum_p / n,
            "actual_rate":  sum_a / n,
            "mean_residual": (sum_p / n) - (sum_a / n),
        }

    # Group by (market, dim, slice_value)
    grouped: Dict[Tuple[str, str, Any], List[Dict[str, Any]]] = {}
    for r in props:
        market = r.get("market")
        if not market:
            continue
        for dim, slicer in SLICERS:
            val = slicer(r)
            if val is None:
                continue
            grouped.setdefault((market, dim, val), []).append(r)

    slices: List[Dict[str, Any]] = []
    for (market, dim, val), recs in grouped.items():
        m = _slice_metrics(recs)
        if not m:
            continue
        # Compute EXTRA bias above the market baseline. Bulk-market
        # calibration handles `mean_residual` already; what's actionable
        # at the context level is `extra_residual` (this slice minus bulk).
        baseline_resid = (market_baseline.get(market) or {}).get("mean_residual", 0.0)
        extra = m["mean_residual"] - baseline_resid
        m["extra_residual"] = round(extra, 4)
        # Filter to "interesting" slices: significant z OR large extra bias
        # over the bulk-market mean (which the market correction already fixes).
        if abs(extra) < BIAS_THRESHOLD and abs(m["z_score"]) < Z_THRESHOLD:
            continue
        note_parts = []
        if val is True:
            note_parts.append({"park_is_indoor": "indoor", "is_night_game": "night",
                               "is_home": "home"}.get(dim, str(val)))
        elif val is False:
            note_parts.append({"park_is_indoor": "outdoor", "is_night_game": "day",
                               "is_home": "road"}.get(dim, str(val)))
        else:
            note_parts.append(f"vs {val}HP" if dim == "opp_pitcher_throws" else str(val))
        direction = "over" if extra > 0 else "under"
        note_parts.append(f"{market.replace('_', ' ')}")
        note_parts.append(f"runs {direction} bulk by {abs(extra)*100:.1f}pp")
        slices.append({
            "market": market,
            "dim": dim,
            "slice_value": val,
            **m,
            "note": " ".join(note_parts),
            "market_baseline_residual": round(baseline_resid, 4),
        })

    # Sort by |extra_residual| then |z_score|
    slices.sort(key=lambda s: (-abs(s["extra_residual"]), -abs(s["z_score"])))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_slice_n": MIN_SLICE_N,
        "bias_threshold": BIAS_THRESHOLD,
        "z_threshold": Z_THRESHOLD,
        "max_correction": MAX_CORRECTION,
        "n_significant": len(slices),
        "slices": slices[:50],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_significant']} significant slices")
    for s in p["slices"][:8]:
        print(f"  [{s['dim']}={s['slice_value']}] {s['market']:25} "
              f"n={s['n']:5} cf={s['correction_factor']} z={s['z_score']}")
