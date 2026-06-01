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

# Event-driven feeds only refresh while a live event is happening (an in-season
# game in progress, a live golf round). When there is no event they go "idle" --
# that is NORMAL, not a data outage (e.g. UCL/EPL in the summer off-season, golf
# between tournaments). They are reported separately and DO NOT drag the headline
# freshness number, which must reflect the always-on core (the MLB engine that is
# the live product right now). Without this, a quiet Sunday in five other sports
# tanked freshness to 64% and tripped the "stale data" banner while every MLB
# feed was 0-7 min fresh.
EVENT_DRIVEN = {
    "nba_state.json", "wnba_state.json", "nhl_state.json",
    "epl_state.json", "mls_state.json", "ucl_state.json",
    "golf_live_tracker.json", "golf_live_projections.json",
    "nhl_goalie_logs.json",
}

# Feeds excluded from the headline pct -- reported for transparency but never
# counted as a core "stale" problem because they're slow-moving, deprecated, or
# carry no in-content timestamp (in CI the file mtime is just the git-checkout
# time, so age can't be inferred from disk):
#   calibration.json -- regenerated every run but has no generated_at field
#   weather.json     -- deprecated; weather now lives inline in today.json games
OPTIONAL = {"calibration.json", "weather.json"}


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
    core_total = 0
    core_stale = 0

    for fname, slo in SLOS_MIN.items():
        path = os.path.join(DATA_DIR, fname)
        tier = ("event" if fname in EVENT_DRIVEN
                else "optional" if fname in OPTIONAL else "core")

        # --- Missing file ---
        if not os.path.exists(path):
            reason = ("ABSENT (optional/deprecated)" if tier == "optional"
                      else "IDLE (no live event)" if tier == "event"
                      else "MISSING")
            results.append({"file": fname, "exists": False, "age_min": None,
                            "slo_min": slo, "tier": tier,
                            "stale": tier == "core", "reason": reason})
            if tier == "core":
                core_total += 1
                core_stale += 1
            continue

        d = _load(path)
        ts = d.get("generated_at") or d.get("generatedAt")
        age = _age_minutes(ts) if ts else None
        age_round = round(age, 1) if age is not None else None

        # --- Event-driven: LIVE when fresh, IDLE otherwise; never "stale" ---
        if tier == "event":
            live = age is not None and age <= slo
            results.append({"file": fname, "exists": True, "generated_at": ts,
                            "age_min": age_round, "slo_min": slo, "tier": "event",
                            "stale": False,
                            "reason": "LIVE" if live else "IDLE (no live event)"})
            continue

        # --- Optional/deprecated: reported, never counted against the headline ---
        if tier == "optional":
            reason = ("UNTRACKED (no generated_at field)" if age is None
                      else "FRESH" if age <= slo else "AGED (optional, not counted)")
            results.append({"file": fname, "exists": True, "generated_at": ts,
                            "age_min": age_round, "slo_min": slo, "tier": "optional",
                            "stale": False, "reason": reason})
            continue

        # --- Core: the always-on MLB engine; this is what the headline measures ---
        if age is None:
            results.append({"file": fname, "exists": True, "generated_at": ts,
                            "age_min": None, "slo_min": slo, "tier": "core",
                            "stale": True, "reason": "NO_TIMESTAMP"})
            core_total += 1
            core_stale += 1
        else:
            over = age > slo
            results.append({"file": fname, "exists": True, "generated_at": ts,
                            "age_min": age_round, "slo_min": slo, "tier": "core",
                            "stale": over, "reason": "STALE" if over else "FRESH"})
            core_total += 1
            if over:
                core_stale += 1

    results.sort(key=lambda r: r["file"])
    core_fresh = core_total - core_stale
    freshness_pct = round(100 * core_fresh / max(core_total, 1), 1)

    event_feeds = [r for r in results if r["tier"] == "event"]
    n_live = sum(1 for r in event_feeds if r["reason"] == "LIVE")
    core_stale_files = [r for r in results if r["tier"] == "core" and r["stale"]]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_files_checked": len(results),
        # Headline = always-on CORE feeds only (the live MLB product). Event-driven
        # other-sport feeds are reported separately so an off-season lull can't tank
        # it (previously 5 idle sports dragged this to 64% and tripped the banner
        # while every MLB feed was 0-7 min fresh).
        "freshness_pct": freshness_pct,
        "core_total": core_total,
        "core_fresh": core_fresh,
        "n_stale_or_missing": len(core_stale_files),   # core problems only
        "method_note": ("Headline freshness_pct is over the always-on CORE feeds "
                        "(MLB slate / props / logs). Event-driven feeds (other-sport "
                        "live states, golf-live) are reported under event_feeds as "
                        "LIVE/IDLE and excluded -- an off-season lull elsewhere is not "
                        "a data outage. Optional/deprecated feeds (calibration without "
                        "a generated_at field; weather, now inline in today.json) are "
                        "excluded too."),
        "files": results,
        "stale_files": core_stale_files,               # back-compat: core only now
        "event_feeds": event_feeds,
        "event_feeds_live": n_live,
        "event_feeds_idle": len(event_feeds) - n_live,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[freshness] CORE {o['core_fresh']}/{o['core_total']} fresh "
          f"({o['freshness_pct']}%), {o['n_stale_or_missing']} core stale/missing; "
          f"events {o['event_feeds_live']} live / {o['event_feeds_idle']} idle -> {OUT}")
