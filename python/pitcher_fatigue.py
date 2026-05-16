"""
EdgeStat -- pitcher fatigue + workload trend.

For every starting pitcher on tonight's slate, derives a fatigue grade
from their pitch_count_history (already cached in matchups.json) plus
gamelog rest gap. Tells Brandon which SPs are at risk of an early hook
(short outing = OVER on opposing-team props, UNDER on SP Ks).

Inputs:
  matchups.json: per-pitcher pitch_count_history { n_starts, avg_pc,
                  max_pc, last_pc, trend (slope), dates[], pcs[] }
  player_gamelogs.json (pitcher gamelogs): date sequence -> rest days

Output: data/pitcher_fatigue.json
  {
    "generated_at": "...",
    "by_pitcher": [
      {
        "name": "Yamamoto",
        "id": ..., "team": "LAD", "matchup": "LAD @ SDP",
        "n_starts": 5, "avg_pc": 92.4, "max_pc": 108, "last_pc": 95,
        "trend": +3.2,                  # slope (pos = climbing workload)
        "days_rest": 4,
        "fatigue_grade": "B",            # A (fresh) -> F (gassed)
        "fatigue_note": "...",
        "expected_pc_range": [86, 102],
        "early_hook_risk": "low",        # low / medium / high
        "ks_lean": "OVER" | "UNDER" | "neutral",   # implication for K props
        "opposing_team_ou_lean": "OVER" | "UNDER" | "neutral",
      }
    ]
  }

Free, no API calls -- pure derivation.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
GAMELOGS_PATH = os.path.join(DATA_DIR, "player_gamelogs.json")
OUT_PATH = os.path.join(DATA_DIR, "pitcher_fatigue.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _days_rest(pid: int, gamelogs: Dict[str, Any]) -> Optional[int]:
    """Days between most recent start and today."""
    gl = gamelogs.get(str(pid)) or gamelogs.get(pid)
    if not gl or not gl.get("games"):
        return None
    today = dt.date.today()
    most_recent_date = None
    for g in gl["games"]:
        d = g.get("date")
        if not d:
            continue
        try:
            game_d = dt.date.fromisoformat(d)
            if game_d < today and (most_recent_date is None or game_d > most_recent_date):
                most_recent_date = game_d
        except Exception:
            continue
    if not most_recent_date:
        return None
    return (today - most_recent_date).days


def _fatigue_grade(pch: Dict[str, Any], days_rest: Optional[int]) -> Dict[str, Any]:
    """Compute grade A-F + early-hook risk + K/OU leans."""
    n = pch.get("n_starts", 0)
    avg_pc = pch.get("avg_pc", 0)
    max_pc = pch.get("max_pc", 0)
    last_pc = pch.get("last_pc", 0)
    trend = pch.get("trend", 0)   # slope across pcs[]

    # Default
    grade = "C"
    note_parts = []
    early_hook_risk = "low"
    ks_lean = "neutral"
    ou_lean = "neutral"

    # Red flags
    red = 0
    if days_rest is not None and days_rest <= 3:
        red += 2
        note_parts.append(f"only {days_rest}d rest")
    if last_pc and last_pc >= 105:
        red += 1
        note_parts.append(f"last start {last_pc} pitches (heavy)")
    if trend > 8:
        red += 1
        note_parts.append(f"workload trending UP ({trend:+.1f}/start)")
    if avg_pc and max_pc and (max_pc - avg_pc) > 25:
        red += 1
        note_parts.append("high variance in recent workload")
    if n and n < 3:
        red += 1
        note_parts.append(f"only {n} starts to draw on")

    # Green flags
    green = 0
    if days_rest is not None and days_rest >= 5:
        green += 1
        note_parts.append(f"{days_rest}d rest (extra)")
    if trend < -5:
        green += 1
        note_parts.append(f"managed workload (trend {trend:+.1f}/start)")
    if last_pc and last_pc <= 80:
        green += 1
        note_parts.append(f"last start light ({last_pc} pitches)")

    # Net grade
    net = green - red
    if net >= 2:    grade = "A"
    elif net == 1:  grade = "B"
    elif net == 0:  grade = "C"
    elif net == -1: grade = "D"
    else:           grade = "F"

    # Early hook risk = red flags only (rest + recent heavy + climbing trend)
    if red >= 3:    early_hook_risk = "high"
    elif red >= 2:  early_hook_risk = "medium"
    else:           early_hook_risk = "low"

    # Implied prop leans:
    # - K props: if early hook expected, lean UNDER on SP K props
    # - Opposing team OU: gassed SP -> more runs allowed -> OVER lean
    if early_hook_risk == "high":
        ks_lean = "UNDER"
        ou_lean = "OVER"
    elif early_hook_risk == "low" and grade in ("A", "B") and last_pc and last_pc < 90:
        # Fresh SP = expect deeper outing = more Ks (but doesn't change OU
        # without knowing K profile)
        ks_lean = "OVER"

    # Expected PC range = avg ± stdev proxy
    if n >= 3 and avg_pc:
        spread = max(5, (max_pc - avg_pc) / 2) if max_pc else 8
        pc_range = [int(avg_pc - spread), int(avg_pc + spread)]
    else:
        pc_range = None

    return {
        "fatigue_grade": grade,
        "fatigue_note": "; ".join(note_parts) or "no notable signals",
        "early_hook_risk": early_hook_risk,
        "ks_lean": ks_lean,
        "opposing_team_ou_lean": ou_lean,
        "expected_pc_range": pc_range,
    }


def run() -> Dict[str, Any]:
    m = _load(MATCHUPS_PATH)
    gl = (_load(GAMELOGS_PATH).get("by_player_id") or {})
    out: List[Dict[str, Any]] = []
    for g in m.get("games") or []:
        matchup = g.get("matchup")
        for side, p_side in (("away", "away_pitcher"), ("home", "home_pitcher")):
            p = g.get(p_side) or {}
            pch = p.get("pitch_count_history") or {}
            if not p.get("id") or not pch.get("n_starts"):
                continue
            days_rest = _days_rest(p["id"], gl)
            grade_info = _fatigue_grade(pch, days_rest)
            out.append({
                "id": p["id"], "name": p.get("name"), "hand": p.get("hand"),
                "matchup": matchup, "side": side,
                "n_starts": pch.get("n_starts"),
                "avg_pc": pch.get("avg_pc"),
                "max_pc": pch.get("max_pc"),
                "last_pc": pch.get("last_pc"),
                "trend": pch.get("trend"),
                "days_rest": days_rest,
                **grade_info,
            })
    # Sort: highest risk first
    risk_order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda r: risk_order.get(r["early_hook_risk"], 9))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_pitchers": len(out),
        "by_pitcher": out,
        "high_risk": [r["name"] for r in out if r["early_hook_risk"] == "high"],
        "fresh": [r["name"] for r in out if r["fatigue_grade"] == "A"],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_pitchers']} pitchers analyzed")
    print(f"  HIGH risk early hook: {p['high_risk']}")
    print(f"  FRESH (grade A):      {p['fresh']}")
