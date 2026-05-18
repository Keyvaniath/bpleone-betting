"""
EdgeStat -- training convergence tracker.

For each market, track whether the calibration correction is CONVERGING
(model becoming more accurate over time) or DIVERGING (model has a
structural problem that calibration can't fix).

Reads training_feedback.json which has 24+ entries of cf_delta over time.
For each market, computes:
  - 7-day rolling abs(cf_delta) -- smaller means converging
  - direction trend -- consistent sign means systematic bias remains
  - convergence score: 0-100 (100 = perfect, calibration is dialing in)

Output: data/training_convergence.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from collections import defaultdict
from statistics import mean, median, stdev
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "training_convergence.json")


def _load(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    fb = _load("training_feedback.json")
    entries = fb.get("entries") or []
    # Group calibration moves by market
    by_market: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        ts = entry.get("ts")
        for move in (entry.get("calibration_moves") or []):
            mk = move.get("market")
            if not mk: continue
            by_market[mk].append({
                "ts": ts,
                "cf_from": move.get("cf_from"),
                "cf_to": move.get("cf_to"),
                "cf_delta": move.get("cf_delta"),
                "n_added": move.get("n_added", 0),
            })

    results: List[Dict[str, Any]] = []
    for mk, moves in by_market.items():
        moves.sort(key=lambda m: m["ts"] or "")
        # Compute convergence metric
        deltas = [abs(m["cf_delta"]) for m in moves if m.get("cf_delta") is not None]
        if not deltas:
            results.append({"market": mk, "n_observations": len(moves),
                             "convergence_score": None, "verdict": "insufficient data"})
            continue
        # Use last 7 observations as recent window
        recent_n = min(7, len(deltas))
        recent_deltas = deltas[-recent_n:]
        avg_abs_delta = mean(recent_deltas)
        # Convergence: smaller abs delta = better
        # 100 at avg_delta=0, 0 at avg_delta=0.05 (5pp swing daily = unstable)
        conv_score = max(0, min(100, 100 * (1 - avg_abs_delta / 0.05)))

        # Directionality: are deltas all same-sign (systematic bias remains)?
        signed_deltas = [m["cf_delta"] for m in moves[-recent_n:] if m.get("cf_delta") is not None]
        if signed_deltas:
            pos = sum(1 for d in signed_deltas if d > 0)
            neg = sum(1 for d in signed_deltas if d < 0)
            same_sign_ratio = max(pos, neg) / len(signed_deltas)
        else:
            same_sign_ratio = 0
        # If consistently same direction, model has unresolved bias
        directional_bias = same_sign_ratio >= 0.8 and len(signed_deltas) >= 3

        # Latest correction_factor
        latest = moves[-1].get("cf_to")
        cf_distance_from_unity = abs((latest or 1) - 1)

        # Final verdict
        if directional_bias:
            verdict = "DIVERGENT - consistent same-sign moves (structural issue)"
            tier = "DEGRADED"
        elif conv_score >= 80:
            verdict = "CONVERGING - calibration dialing in"
            tier = "ELITE"
        elif conv_score >= 60:
            verdict = "STABLE - small adjustments only"
            tier = "HEALTHY"
        elif conv_score >= 40:
            verdict = "ADJUSTING - mid-size daily moves"
            tier = "OK"
        else:
            verdict = "UNSTABLE - large daily swings"
            tier = "DEGRADED"

        results.append({
            "market": mk,
            "n_observations": len(moves),
            "n_in_window": recent_n,
            "avg_abs_delta_7d": round(avg_abs_delta, 4),
            "convergence_score": round(conv_score, 1),
            "directional_bias": directional_bias,
            "same_sign_ratio": round(same_sign_ratio, 3),
            "latest_correction_factor": round(latest, 4) if latest else None,
            "cf_distance_from_unity": round(cf_distance_from_unity, 4),
            "verdict": verdict,
            "tier": tier,
        })

    # Sort by convergence score
    results.sort(key=lambda r: -(r.get("convergence_score") or 0))
    summary = {"ELITE": 0, "HEALTHY": 0, "OK": 0, "DEGRADED": 0}
    for r in results:
        t = r.get("tier")
        if t in summary: summary[t] += 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_markets_tracked": len(results),
        "n_observations_total": sum(r["n_observations"] for r in results),
        "tier_summary": summary,
        "markets": results,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Training convergence: {p['n_markets_tracked']} markets across {p['n_observations_total']} observations")
    print(f"Tiers: {p['tier_summary']}")
    print()
    for r in p["markets"]:
        flag = "!" if r.get("directional_bias") else " "
        print(f" {flag} {r['market']:25s} [{r['tier']:8s}] score={r.get('convergence_score','?')} avg_delta={r.get('avg_abs_delta_7d','?')} cf={r.get('latest_correction_factor','?')}")
        print(f"      {r['verdict']}")
