"""
EdgeStat -- model calibration status snapshot.

Aggregates calibration health into a single JSON the dashboard can render.
Surfaces:
   how raw probabilities are shrunk per source
   which sports currently have real market lines (shrinkage anchors)
   the gap between raw model output and calibrated output across the slate
   a "calibration progress" score driven by settled locks (sample size)

This is the transparency layer: visitors see WHY a model 92% becomes a
displayed 72%, instead of getting an unexplained number.

Output: data/calibration_status.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "calibration_status.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    locks = _load(os.path.join(DATA_DIR, "locks_history.json"))

    calibration_meta = top_plays.get("calibration") or {}
    all_plays = top_plays.get("all_plays") or top_plays.get("top_25") or []

    # Aggregate raw vs calibrated probabilities across all plays
    pairs = []
    by_source: Dict[str, Dict[str, Any]] = {}
    for p in all_plays:
        raw = p.get("raw_prob")
        cal = p.get("prob")
        if raw is None or cal is None: continue
        pairs.append((raw, cal))
        src = p.get("source") or "unknown"
        if src not in by_source:
            by_source[src] = {"n": 0, "sum_raw": 0.0, "sum_cal": 0.0,
                                "max_raw": 0.0, "shrinkage_w": p.get("shrinkage_w")}
        b = by_source[src]
        b["n"] += 1
        b["sum_raw"] += raw
        b["sum_cal"] += cal
        b["max_raw"] = max(b["max_raw"], raw)

    for src, b in by_source.items():
        if b["n"] > 0:
            b["avg_raw_prob"] = round(b["sum_raw"] / b["n"], 4)
            b["avg_cal_prob"] = round(b["sum_cal"] / b["n"], 4)
            b["avg_compression_pp"] = round((b["avg_raw_prob"] - b["avg_cal_prob"]) * 100, 1)
        del b["sum_raw"]
        del b["sum_cal"]

    # Average compression across all plays
    if pairs:
        avg_raw = sum(r for r, _ in pairs) / len(pairs)
        avg_cal = sum(c for _, c in pairs) / len(pairs)
        avg_compression = (avg_raw - avg_cal) * 100
        max_raw = max(r for r, _ in pairs)
    else:
        avg_raw = avg_cal = avg_compression = max_raw = None

    # Calibration progress driven by settled locks (sample size)
    n_settled = locks.get("n_settled") or 0
    if n_settled >= 100:
        cal_progress = 100
        cal_tier = "PRODUCTION"
        cal_note = "Sufficient settled outcomes -- calibration is data-driven."
    elif n_settled >= 30:
        cal_progress = 70
        cal_tier = "REFINING"
        cal_note = "30+ settled outcomes -- per-source shrinkage tuning kicks in."
    elif n_settled >= 8:
        cal_progress = 40
        cal_tier = "BOOTSTRAPPING"
        cal_note = "8+ settled outcomes -- initial bias corrections active."
    else:
        cal_progress = 10
        cal_tier = "PRE-CALIBRATION"
        cal_note = f"Only {n_settled} settled outcomes -- using shrinkage priors. First real calibration data lands tomorrow."

    # Identify sports with real market data (have fair_american explicitly set
    # on most plays, meaning shrinkage anchors to market)
    sports_with_market: Dict[str, int] = {}
    sports_without_market: Dict[str, int] = {}
    for p in all_plays:
        sp = p.get("sport") or "?"
        fair = p.get("fair_american")
        # Default fair odds (-110 or -136) don't count as "real market data";
        # only explicitly-provided market lines do
        has_real_market = isinstance(fair, (int, float)) and fair not in (-110, -136)
        d = sports_with_market if has_real_market else sports_without_market
        d[sp] = d.get(sp, 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "calibration_tier": cal_tier,
        "calibration_progress_pct": cal_progress,
        "calibration_note": cal_note,
        "n_settled_locks": n_settled,
        "n_locks_pending": locks.get("n_pending") or 0,
        "shrinkage_baseline_prob": calibration_meta.get("shrinkage_baseline_prob"),
        "default_shrinkage_w": calibration_meta.get("default_shrinkage_w"),
        "per_source_shrinkage_w": calibration_meta.get("per_source_w") or {},
        "n_plays_calibrated": len(pairs),
        "avg_raw_prob": round(avg_raw, 4) if avg_raw is not None else None,
        "avg_calibrated_prob": round(avg_cal, 4) if avg_cal is not None else None,
        "avg_compression_pp": round(avg_compression, 1) if avg_compression is not None else None,
        "max_raw_prob": round(max_raw, 4) if max_raw is not None else None,
        "by_source": by_source,
        "sports_with_market_anchor": sports_with_market,
        "sports_without_market_anchor": sports_without_market,
        "transparency_note": (
            "Raw model probabilities are shrunk toward market-implied "
            "probabilities (when available) or a 0.55 baseline. This "
            "compresses small-sample overconfidence into realistic ranges. "
            "Edges in the displayed top plays board are post-calibration."
        ),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Calibration Status: {p['calibration_tier']} ({p['calibration_progress_pct']}%)")
    print(f"  {p['calibration_note']}")
    print(f"  Settled locks: {p['n_settled_locks']} | Pending: {p['n_locks_pending']}")
    print(f"  Avg compression: {p.get('avg_compression_pp', 0):.1f}pp (raw {p.get('avg_raw_prob', 0):.3f} -> cal {p.get('avg_calibrated_prob', 0):.3f})")
    print(f"  Max raw prob seen: {p.get('max_raw_prob', 0):.3f}")
    print(f"\n  By source:")
    for src, b in sorted(p["by_source"].items(), key=lambda kv: -kv[1]["n"])[:8]:
        print(f"    {src:30s}  n={b['n']:4d}  w={b['shrinkage_w']:.2f}  raw avg {b['avg_raw_prob']:.3f} -> cal {b['avg_cal_prob']:.3f}  ({b['avg_compression_pp']:+.1f}pp)")
    print(f"\n  Sports WITH market anchor: {p['sports_with_market_anchor']}")
    print(f"  Sports WITHOUT market anchor: {p['sports_without_market_anchor']}")
