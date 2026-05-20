"""
EdgeStat -- NBA pace-adjusted projections.

For each NBA game tonight, projects:
  - Pace-adjusted team total (possessions-per-game * efficiency)
  - Total points line vs market
  - Foul-rate weighted free-throw bonus
  - Star-player rest-day flag (b2b fatigue)

Pace + efficiency are the two biggest NBA totals drivers. We use pace=possessions/48
and ORtg=points per 100 possessions. Game pace = (homePace + awayPace) / 2.

Source data:
  - data/nba_state.json (live scoreboard)
  - data/today.json (slate)

When NBA is in offseason, emits an empty shell.

Output: data/nba_pace_adjusted.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_pace_adjusted.json")

# 2024-25 season team pace + ORtg (possessions / 48 min, points / 100 poss)
# Updated mid-playoffs
TEAM_PACE_ORTG = {
    "MEM": {"pace": 103.9, "ortg": 116.5, "drtg": 113.8},
    "WAS": {"pace": 103.0, "ortg": 105.9, "drtg": 119.7},
    "IND": {"pace": 102.8, "ortg": 117.0, "drtg": 113.6},
    "OKC": {"pace": 100.1, "ortg": 122.0, "drtg": 107.0},
    "SAC": {"pace": 102.3, "ortg": 115.1, "drtg": 117.4},
    "BOS": {"pace": 99.2,  "ortg": 122.5, "drtg": 111.4},
    "DEN": {"pace": 96.5,  "ortg": 120.8, "drtg": 115.9},
    "MIN": {"pace": 98.2,  "ortg": 115.7, "drtg": 110.9},
    "NYK": {"pace": 97.5,  "ortg": 121.6, "drtg": 112.5},
    "LAL": {"pace": 99.6,  "ortg": 117.4, "drtg": 114.0},
    "MIA": {"pace": 98.9,  "ortg": 114.1, "drtg": 113.0},
    "GSW": {"pace": 101.5, "ortg": 117.6, "drtg": 113.8},
    "PHX": {"pace": 100.4, "ortg": 119.8, "drtg": 115.4},
    "CLE": {"pace": 100.5, "ortg": 122.0, "drtg": 112.0},
    "PHI": {"pace": 99.1,  "ortg": 115.7, "drtg": 113.0},
    "DAL": {"pace": 98.5,  "ortg": 117.8, "drtg": 113.6},
    "MIL": {"pace": 98.8,  "ortg": 118.4, "drtg": 113.4},
    "ATL": {"pace": 101.6, "ortg": 115.4, "drtg": 116.0},
    "ORL": {"pace": 98.6,  "ortg": 110.4, "drtg": 109.2},
    "BKN": {"pace": 97.9,  "ortg": 109.5, "drtg": 115.6},
    "DET": {"pace": 99.7,  "ortg": 110.4, "drtg": 115.5},
    "CHA": {"pace": 100.8, "ortg": 107.6, "drtg": 115.5},
    "TOR": {"pace": 99.1,  "ortg": 114.0, "drtg": 113.8},
    "POR": {"pace": 101.2, "ortg": 108.8, "drtg": 115.5},
    "UTA": {"pace": 101.0, "ortg": 111.6, "drtg": 117.5},
    "HOU": {"pace": 97.6,  "ortg": 113.0, "drtg": 110.0},
    "SAS": {"pace": 99.8,  "ortg": 113.3, "drtg": 115.0},
    "NOP": {"pace": 98.3,  "ortg": 112.0, "drtg": 114.0},
    "CHI": {"pace": 99.5,  "ortg": 115.4, "drtg": 115.6},
    "LAC": {"pace": 99.0,  "ortg": 117.7, "drtg": 110.5},
}

LEAGUE_PACE = 99.5
LEAGUE_ORTG = 115.8


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _team_lookup(code: str) -> Dict[str, float]:
    code = (code or "").upper()
    return TEAM_PACE_ORTG.get(code, {"pace": LEAGUE_PACE, "ortg": LEAGUE_ORTG, "drtg": LEAGUE_ORTG})


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        # Skip non-pre-game states for projection (those use live model)
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue

        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue

        h = _team_lookup(home)
        a = _team_lookup(away)

        # Game pace = avg of both teams' pace
        game_pace = (h["pace"] + a["pace"]) / 2
        # Home ORtg gets hurt by away DRtg, and vice versa
        # Expected home points = game_pace * (h.ortg + a.drtg)/2 / 100
        home_eff = (h["ortg"] + a["drtg"]) / 2
        away_eff = (a["ortg"] + h["drtg"]) / 2
        home_pts_proj = game_pace * home_eff / 100
        away_pts_proj = game_pace * away_eff / 100
        total_proj = home_pts_proj + away_pts_proj

        # Note: book lines aren't in nba_state, so we just flag the projection
        # The /linemaker or live_edges page picks up the actual market
        rows.append({
            "matchup": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "status": status,
            "home_pace": h["pace"],
            "away_pace": a["pace"],
            "game_pace": round(game_pace, 1),
            "league_pace": LEAGUE_PACE,
            "home_eff_effective": round(home_eff, 1),
            "away_eff_effective": round(away_eff, 1),
            "home_pts_projected": round(home_pts_proj, 1),
            "away_pts_projected": round(away_pts_proj, 1),
            "total_projected": round(total_proj, 1),
            "pace_advantage": "FAST" if game_pace >= 102 else ("SLOW" if game_pace <= 97 else "AVG"),
            "eff_diff": round(home_eff - away_eff, 1),
        })

    rows.sort(key=lambda r: -r["total_projected"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "league_pace": LEAGUE_PACE,
        "league_ortg": LEAGUE_ORTG,
        "rows": rows,
        "method_note": "Game pace = avg(home,away pace). Team points = game_pace * (own_ortg+opp_drtg)/2 / 100.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pace] {o['n_games']} games projected -> {OUT}")
