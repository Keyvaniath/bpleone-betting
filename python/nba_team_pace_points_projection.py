"""
EdgeStat -- NBA team pace + points projection.

Pure-model (no odds needed). Projects each team's expected points and the
game total from pace + offensive/defensive efficiency:

  team_pts = projected_pace/100 * ORtg_adjusted
  ORtg_adjusted = own_ORtg * (opp_DRtg / league_DRtg)
  game_total = home_pts + away_pts

Anchors team-total and game-total leans independent of book lines.

Output: data/nba_team_pace_points_projection.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_team_pace_points_projection.json")

LEAGUE_ORTG = 114.0
LEAGUE_DRTG = 114.0
LEAGUE_PACE = 100.0


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def run() -> Dict[str, Any]:
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))

    rows: List[Dict[str, Any]] = []
    for g in (pace.get("games") or pace.get("rows") or []):
        if not isinstance(g, dict): continue
        matchup = g.get("matchup") or ""
        proj_pace = _safe(g.get("projected_pace") or g.get("pace"), LEAGUE_PACE)

        home_ortg = _safe(g.get("home_ortg"), LEAGUE_ORTG)
        away_ortg = _safe(g.get("away_ortg"), LEAGUE_ORTG)
        home_drtg = _safe(g.get("home_drtg"), LEAGUE_DRTG)
        away_drtg = _safe(g.get("away_drtg"), LEAGUE_DRTG)

        # Possessions estimate from pace
        poss = proj_pace
        # Adjusted offensive ratings vs opp defense
        home_ortg_adj = home_ortg * (away_drtg / LEAGUE_DRTG)
        away_ortg_adj = away_ortg * (home_drtg / LEAGUE_DRTG)

        home_pts = poss / 100.0 * home_ortg_adj
        away_pts = poss / 100.0 * away_ortg_adj
        game_total = home_pts + away_pts

        rows.append({
            "matchup": matchup,
            "projected_pace": round(proj_pace, 1),
            "projected_home_pts": round(home_pts, 1),
            "projected_away_pts": round(away_pts, 1),
            "projected_game_total": round(game_total, 1),
            "projected_margin": round(home_pts - away_pts, 1),
        })

    rows.sort(key=lambda r: -r["projected_game_total"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "method_note": "Pure-model NBA pace+points projection. poss = projected_pace; "
                       "ORtg_adj = own_ORtg * (opp_DRtg/league). team_pts = "
                       "poss/100 * ORtg_adj. game_total = home+away. League "
                       "ORtg/DRtg=114, pace=100 defaults.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pace-pts] {o['n_games']} games projected -> {OUT}")
