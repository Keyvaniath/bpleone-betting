"""
EdgeStat -- bullpen exhaustion alert.

Reads bullpen_workload.json (already produced daily) and flags per team:
  - GASSED: cumulative reliever IP >= 6 in last 2 days
  - WORN: cumulative IP 4-6
  - FRESH: < 4 IP across all relievers

Joins with tonight's matchups to produce a per-game implication:
  - Both teams GASSED: late-inning OVER bias, total OVER lean
  - Home GASSED + Away FRESH: late-game momentum AWAY (away leading
    after 5 is now more likely to hold)

Output: data/bullpen_alert.json
  {
    "generated_at": "...",
    "by_team": {...},
    "by_game": [
      { matchup, home_status, away_status, late_inning_ou_lean, note }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BULLPEN_PATH = os.path.join(DATA_DIR, "bullpen_workload.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "bullpen_alert.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _classify(total_ip: Optional[float]) -> str:
    if total_ip is None:
        return "unknown"
    if total_ip >= 6:
        return "GASSED"
    if total_ip >= 4:
        return "WORN"
    return "FRESH"


def run() -> Dict[str, Any]:
    bp = _load(BULLPEN_PATH)
    matchups = _load(MATCHUPS_PATH)

    teams = bp.get("teams") or {}
    by_team_out: Dict[str, Dict[str, Any]] = {}
    by_team_id: Dict[int, Dict[str, Any]] = {}
    for name, info in teams.items():
        ip = info.get("total_relief_ip")
        rec = {
            "name": name,
            "abbr": info.get("abbr") or name,
            "total_relief_ip": ip,
            "games_inspected": info.get("games_inspected"),
            "status": _classify(ip),
        }
        by_team_out[name] = rec
        by_team_out[info.get("abbr") or name] = rec
        if info.get("team_id"):
            by_team_id[int(info["team_id"])] = rec

    # Per-game lean. matchups.json schema: home/away are dicts containing
    # team_id, not plain names. Use that to join with bullpen_workload.
    games_out: List[Dict[str, Any]] = []
    for g in matchups.get("games") or []:
        home_obj = g.get("home") or {}
        away_obj = g.get("away") or {}
        h_id = home_obj.get("team_id") if isinstance(home_obj, dict) else None
        a_id = away_obj.get("team_id") if isinstance(away_obj, dict) else None
        # Fallback: matchup string "AWAY @ HOME"
        matchup = g.get("matchup") or ""
        away_abbr, home_abbr = (matchup.split(" @ ") + [None, None])[:2]
        h_info = (by_team_id.get(h_id) if h_id else None) or by_team_out.get(home_abbr) or {}
        a_info = (by_team_id.get(a_id) if a_id else None) or by_team_out.get(away_abbr) or {}
        h_st = h_info.get("status", "unknown")
        a_st = a_info.get("status", "unknown")
        # Late-inning OU lean
        lean = "neutral"
        note_parts = []
        if h_st == "GASSED" and a_st == "GASSED":
            lean = "OVER"
            note_parts.append("Both pens gassed -- late-inning runs more likely")
        elif h_st == "GASSED" or a_st == "GASSED":
            side = "home" if h_st == "GASSED" else "away"
            note_parts.append(f"{side.upper()} pen GASSED -- {side}-side runners more dangerous late")
            lean = "OVER"
        if h_st == "FRESH" and a_st == "FRESH":
            note_parts.append("Both pens fresh -- expect clean late innings")
            lean = "UNDER"
        if not note_parts:
            note_parts.append("Mixed workload -- no strong late-game lean")
        games_out.append({
            "matchup": g.get("matchup"),
            "home": h_info.get("name") or home_abbr,
            "away": a_info.get("name") or away_abbr,
            "home_status": h_st, "away_status": a_st,
            "home_ip": h_info.get("total_relief_ip"),
            "away_ip": a_info.get("total_relief_ip"),
            "late_inning_ou_lean": lean,
            "note": "; ".join(note_parts),
        })

    # Sort: games with at least one GASSED first
    games_out.sort(key=lambda g: (0 if "GASSED" in (g["home_status"], g["away_status"]) else 1, g.get("matchup", "")))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_teams": len(by_team_out),
        "n_games": len(games_out),
        "gassed_teams": [n for n, v in by_team_out.items() if v["status"] == "GASSED"],
        "by_team": by_team_out,
        "by_game": games_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Teams: {p['n_teams']}, Games: {p['n_games']}")
    print(f"  GASSED bullpens: {p['gassed_teams']}")
    for g in p["by_game"][:5]:
        print(f"  {g['matchup']:18} home={g['home_status']:6} away={g['away_status']:6} lean={g['late_inning_ou_lean']:7} :: {g['note']}")
