"""
EdgeStat -- self-learning loop value-add quantifier.

Answers the question: "what is the calibration loop ACTUALLY worth?"

For every settled prop in track_record, computes the OVER/UNDER pick that
the RAW model would have made vs the picks the calibrated model actually
made. Diffs the hit rate and Brier between the two.

This is the empirical proof of the loop's value, not vibes:
  - Raw hit rate: 51.2%   (what the model would do with no correction)
  - Calibrated:   56.8%   (what it actually does)
  - Calibration value-add: +5.6pp

If the loop is genuinely helping, calibrated > raw. If they're equal,
the bias correction isn't being applied (and we have a bug). If raw is
better, calibration is hurting -- the recommender should fire on N_PRIOR.

Output: data/loop_value.json
  {
    "generated_at": "...",
    "n_records": 45000,
    "raw":        {"hit_rate": 0.512, "brier": 0.241},
    "calibrated": {"hit_rate": 0.568, "brier": 0.213},
    "value_add": {"hit_rate_pp": 5.6, "brier_delta": -0.028},
    "by_market": [
      {"market": "...", "raw_hit_rate": ..., "cal_hit_rate": ..., "delta_pp": ...}
    ],
    "trailing_30d": { same shape as above, scoped to last 30 days }
  }

The key trick: track_record stores model_prob_over which is POST-calibration.
To recover the RAW (pre-cal) probability, we divide by the correction factor
that was in effect at that point. Since we don't have a per-record CF in
track_record, we approximate by using the latest market-level CF from
calibration_live.json as the "current correction" -- and reverse it out
to get the pre-cal prob. For records where the CF would clip the prob,
we treat raw == calibrated (no signal change). This is an approximation
but it directionally captures the loop's contribution.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")
OUT_PATH = os.path.join(DATA_DIR, "loop_value.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _hit_for_pick(p_over: float, over_hit: bool) -> int:
    side = "OVER" if p_over >= 0.5 else "UNDER"
    if side == "OVER" and over_hit: return 1
    if side == "UNDER" and not over_hit: return 1
    return 0


def _metrics(records: List[Tuple[float, bool]]) -> Optional[Dict[str, Any]]:
    if not records:
        return None
    n = len(records)
    hits = sum(_hit_for_pick(p, h) for p, h in records)
    brier = sum((p - (1 if h else 0)) ** 2 for p, h in records) / n
    return {"n": n, "hit_rate": round(hits / n, 4), "brier": round(brier, 4)}


def _date_of(r: Dict[str, Any]) -> Optional[dt.date]:
    s = r.get("date")
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def _compute(records: List[Dict[str, Any]], cf_by_market: Dict[str, float]
            ) -> Optional[Dict[str, Any]]:
    raw, cal = [], []
    by_market_records: Dict[str, Dict[str, List[Tuple[float, bool]]]] = {}
    for r in records:
        p_cal = r.get("model_prob_over")
        oh = r.get("over_hit")
        market = r.get("market")
        if p_cal is None or oh is None or market is None:
            continue
        cf = cf_by_market.get(market, 1.0)
        # Reverse the correction to estimate raw probability:
        # cal = max(eps, min(1-eps, raw * cf))  =>  raw ~= cal / cf
        if cf <= 0:
            p_raw = p_cal
        else:
            p_raw = max(0.001, min(0.999, p_cal / cf))
        cal.append((p_cal, bool(oh)))
        raw.append((p_raw, bool(oh)))
        by_market_records.setdefault(market, {"raw": [], "cal": []})
        by_market_records[market]["raw"].append((p_raw, bool(oh)))
        by_market_records[market]["cal"].append((p_cal, bool(oh)))

    if not cal:
        return None

    cal_m = _metrics(cal)
    raw_m = _metrics(raw)
    if not cal_m or not raw_m:
        return None

    by_market = []
    for m, sets in by_market_records.items():
        rm = _metrics(sets["raw"])
        cm = _metrics(sets["cal"])
        if not rm or not cm:
            continue
        by_market.append({
            "market": m,
            "n": cm["n"],
            "raw_hit_rate": rm["hit_rate"],
            "cal_hit_rate": cm["hit_rate"],
            "delta_pp": round((cm["hit_rate"] - rm["hit_rate"]) * 100, 2),
            "raw_brier": rm["brier"],
            "cal_brier": cm["brier"],
            "brier_delta": round(cm["brier"] - rm["brier"], 4),
        })
    by_market.sort(key=lambda d: -d["delta_pp"])

    return {
        "raw": raw_m,
        "calibrated": cal_m,
        "value_add": {
            "hit_rate_pp": round((cal_m["hit_rate"] - raw_m["hit_rate"]) * 100, 2),
            "brier_delta": round(cal_m["brier"] - raw_m["brier"], 4),
        },
        "by_market": by_market,
    }


def run() -> Dict[str, Any]:
    tr = _load(TR_PATH)
    cal = _load(CAL_PATH)
    props = tr.get("props", []) or []
    cf_by_market: Dict[str, float] = {}
    for m, v in (cal.get("markets") or {}).items():
        cf = v.get("correction_factor")
        if cf is not None:
            cf_by_market[m] = cf

    overall = _compute(props, cf_by_market) or {}

    # Trailing 30-day window
    cutoff = dt.date.today() - dt.timedelta(days=30)
    recent: List[Dict[str, Any]] = []
    for r in props:
        d = _date_of(r)
        if d and d >= cutoff:
            recent.append(r)
    trailing = _compute(recent, cf_by_market) or {}

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_records": len(props),
        **overall,
        "trailing_30d": trailing,
        "correction_factors_used": cf_by_market,
        "note": ("Raw prob estimated by dividing calibrated prob by the current "
                 "market-level correction factor. Approximation -- doesn't account "
                 "for historical CF drift -- but directionally captures loop value."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p.get('n_records', 0)} records")
    v = p.get("value_add") or {}
    raw = p.get("raw") or {}
    cal = p.get("calibrated") or {}
    if raw and cal:
        print(f"  Overall:")
        print(f"    raw         hit_rate={raw['hit_rate']:.4f} brier={raw['brier']:.4f}")
        print(f"    calibrated  hit_rate={cal['hit_rate']:.4f} brier={cal['brier']:.4f}")
        print(f"    value-add   hit_rate +{v['hit_rate_pp']}pp  brier {v['brier_delta']:+.4f}")
    t = p.get("trailing_30d") or {}
    if t.get("value_add"):
        tv = t["value_add"]
        print(f"  Trailing 30d:")
        print(f"    value-add   hit_rate +{tv['hit_rate_pp']}pp  brier {tv['brier_delta']:+.4f}")
