"""
EdgeStat -- data freshness audit.

For every key data file, computes age in minutes since `generated_at` and
flags STALE if older than per-file freshness SLOs.

SLOs (in minutes):
  - matchups.json, today.json, weather.json:  60 min (must be fresh for slate)
  - *_logs.json (pitcher/batter/goalie):     180 min (3h roll-up)
  - *_props.json:                             45 min (output cadence)
  - *_state.json (nba/wnba/nhl/soccer):       30 min (live game updates)
  - calibration / backtest:                  720 min (12h)

Output: data/data_freshness_audit.json
  Includes per-file age + STALE flag, and overall n_stale_files count.

Brandon's directive: "need to make sure data is accurate". This module
gives the answer at a glance.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "data_freshness_audit.json")


SLOS_MIN = {
    # Slate-critical (must be very fresh)
    "matchups.json": 60,
    "today.json": 60,
    "weather.json": 60,
    # Player/team logs (roll-up every few hours)
    "mlb_pitcher_logs.json": 180,
    "mlb_batter_logs.json": 180,
    "nhl_goalie_logs.json": 240,
    # Prop outputs (match batch cadence)
    "alpha_pick_of_day.json": 45,
    "bet_slate.json": 45,
    "confluence_top_5.json": 45,
    "mlb_today_master_brief.json": 45,
    "mlb_today_game_grid.json": 45,
    "cross_sport_alpha_scanner.json": 45,
    "mlb_perfect_storm_alerts.json": 45,
    "mlb_todays_alerts.json": 45,
    "data_integrity_audit.json": 60,
    # Sport states (live game updates)
    "nba_state.json": 30,
    "wnba_state.json": 30,
    "nhl_state.json": 30,
    "epl_state.json": 30,
    "mls_state.json": 30,
    "ucl_state.json": 30,
    "golf_live_tracker.json": 30,
    "golf_live_projections.json": 30,
    # Calibration / backtest (slow-moving)
    "calibration.json": 720,
    "backtest.json": 720,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _age_minutes(timestamp_str: str) -> float:
    """Parse ISO timestamp and return age in minutes from now."""
    if not timestamp_str: return 99999.0
    # Strip any trailing 'Z' and offset
    ts = timestamp_str.replace("Z", "").split("+")[0].split(".")[0]
    try:
        gen = dt.datetime.fromisoformat(ts)
        now = dt.datetime.utcnow()
        delta = now - gen
        return max(0.0, delta.total_seconds() / 60.0)
    except Exception:
        return 99999.0


def run() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    n_stale = 0

    for fname, slo in SLOS_MIN.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            results.append({
                "file": fname,
                "exists": False,
                "age_min": None,
                "slo_min": slo,
                "stale": True,
                "reason": "MISSING",
            })
            n_stale += 1
            continue

        d = _load(path)
        ts = d.get("generated_at") or d.get("generatedAt")
        age = _age_minutes(ts)
        stale = age > slo

        results.append({
            "file": fname,
            "exists": True,
            "generated_at": ts,
            "age_min": round(age, 1),
            "slo_min": slo,
            "stale": stale,
            "reason": "STALE" if stale else "FRESH",
        })
        if stale: n_stale += 1

    # Sort by file name for stable output
    results.sort(key=lambda r: r["file"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_files_checked": len(results),
        "n_stale_or_missing": n_stale,
        "freshness_pct": round(100 * (len(results) - n_stale) / max(len(results), 1), 1),
        "method_note": "Per-file age (minutes) vs SLO threshold. STALE flag set when "
                       "age > SLO. Critical files (matchups/today/weather) have 60min "
                       "SLOs; prop outputs 45min; logs 180min.",
        "files": results,
        "stale_files": [r for r in results if r["stale"]],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[freshness] {o['n_files_checked']} files, "
          f"{o['n_stale_or_missing']} stale/missing, {o['freshness_pct']}% fresh -> {OUT}")
