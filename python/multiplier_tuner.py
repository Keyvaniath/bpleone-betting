"""
EdgeStat -- secondary multiplier tuner.

The projection model uses several multiplicative knobs:
  - opp_mult: opp-team K-rate adjustment (currently [0.75, 1.25])
  - umpire_k_mult: ump zone size effect on K rate
  - park_factor: hits-friendly / pitcher-friendly factor per venue
  - carry_index: wind effect on HR/TB

Each one is hardcoded. As training data accumulates, we can grid-search
the AMPLIFICATION FACTOR on each (i.e., "do we apply the ump effect at
full strength, half, double?") that minimizes RMSE on settled outcomes.

Writes data/multiplier_tuner.json:
  {
    "by_market": {
      "pitcher_strikeouts": {
        "opp_mult_amplifier":    1.0,    # apply at full strength
        "umpire_mult_amplifier": 0.7,    # ump effect over-baked; dampen 30%
        "park_factor_amplifier": 1.0,
        "rmse_default": 2.05,
        "rmse_tuned":   1.96,
      }
    }
  }

props_pipeline can optionally read these and scale each multiplier's
deviation-from-1 by the amplifier. Conservative default: amplifier=1.0
(no change) if the trainer hasn't found a better value yet.
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
OUT_PATH = os.path.join(DATA_DIR, "multiplier_tuner.json")

MIN_SAMPLE = 50          # need >=50 settled with the relevant debug field
AMPLIFIER_GRID = [0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5]


def _load_tr() -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        return {"props": []}
    try:
        with open(TR_PATH) as f:
            return json.load(f)
    except Exception:
        return {"props": []}


def _rmse_with_amplifier(records: List[Dict[str, Any]],
                          mult_field: str,
                          amplifier: float) -> Optional[float]:
    """Compute RMSE on (actual vs (projection adjusted by amplified mult)).

    For each record with debug.<mult_field>, simulate what the projection
    would have been if that multiplier's deviation-from-1 were amplified.
    Example: if opp_mult was 0.85 (15% suppression) and amplifier=0.5,
    we replace it with 1.0 - 0.15*0.5 = 0.925.
    """
    sse = 0.0
    n = 0
    for r in records:
        proj = r.get("model_projection")
        actual = r.get("actual")
        dbg = r.get("debug") or {}
        mult = dbg.get(mult_field)
        if proj is None or actual is None or not isinstance(mult, (int, float)):
            continue
        # Reconstruct base projection: proj / mult = base
        if mult == 0:
            continue
        base = proj / mult
        # Re-apply with amplified deviation
        new_mult = 1.0 + (mult - 1.0) * amplifier
        new_proj = base * new_mult
        sse += (actual - new_proj) ** 2
        n += 1
    if n < MIN_SAMPLE:
        return None
    return math.sqrt(sse / n)


def tune_market(market: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """For one market, grid-search each multiplier amplifier."""
    out = {"n": len(records)}
    # Map market -> list of multiplier debug-fields to tune
    mult_fields = []
    if market == "pitcher_strikeouts":
        mult_fields = [("opp_mult", "opp_mult_amplifier"),
                       ("umpire_k_mult", "umpire_mult_amplifier")]
    elif market in ("batter_total_bases", "batter_home_runs"):
        mult_fields = [("park_hand_mult", "park_hand_amplifier")]
    if not mult_fields:
        out["note"] = "no tunable multipliers for this market"
        return out

    for field, out_key in mult_fields:
        best_amp, best_rmse = 1.0, float("inf")
        default_rmse = _rmse_with_amplifier(records, field, 1.0)
        for amp in AMPLIFIER_GRID:
            rmse = _rmse_with_amplifier(records, field, amp)
            if rmse is None:
                continue
            if rmse < best_rmse:
                best_rmse = rmse
                best_amp = amp
        if default_rmse is not None and best_rmse < float("inf"):
            out[out_key] = round(best_amp, 2)
            out[f"{field}_rmse_default"] = round(default_rmse, 3)
            out[f"{field}_rmse_tuned"]   = round(best_rmse, 3)
            out[f"{field}_improvement"]  = round(default_rmse - best_rmse, 4)
        else:
            out[out_key] = 1.0
            out[f"{field}_note"] = f"insufficient samples with debug.{field}"
    return out


def run() -> Dict[str, Any]:
    tr = _load_tr()
    props = tr.get("props", [])
    by_market: Dict[str, List[Dict[str, Any]]] = {}
    for r in props:
        m = r.get("market")
        if m and r.get("model_projection") is not None and r.get("actual") is not None:
            by_market.setdefault(m, []).append(r)

    out: Dict[str, Any] = {}
    for market, recs in by_market.items():
        out[market] = tune_market(market, recs)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "amplifier_grid": AMPLIFIER_GRID,
        "min_sample": MIN_SAMPLE,
        "by_market": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    for market, info in p["by_market"].items():
        amplifiers = {k: v for k, v in info.items() if k.endswith("_amplifier")}
        improvements = {k: v for k, v in info.items() if k.endswith("_improvement")}
        if amplifiers or info.get("note"):
            print(f"  {market:25} n={info.get('n', '?'):>5} | {amplifiers} | RMSE improvements: {improvements} | {info.get('note', '')}")
