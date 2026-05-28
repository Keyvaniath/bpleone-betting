"""
EdgeStat -- NHL team pace / shot-volume projection.

Pure-model (no odds needed). Projects expected combined shots-on-goal and
goals for each game from team-level pace metrics:
  - Each team's SF/GP (shots for per game) + SA/GP (shots against)
  - Blended game SOG = (home_SF + away_SA)/2 + (away_SF + home_SA)/2
  - Goal pace from league shooting % (~9.5%)

Anchors game-total-SOG and game-total-goals leans independent of book.

Output: data/nhl_team_pace_projection.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_team_pace_projection.json")

LEAGUE_SF_GP = 30.0
LEAGUE_SHOOT_PCT = 0.095


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
    tt = _load(os.path.join(DATA_DIR, "nhl_team_total_edge.json"))
    sog_total = _load(os.path.join(DATA_DIR, "nhl_game_total_sog.json"))

    # Gather team SF/SA per (matchup, side)
    team_metrics: Dict[str, Dict[str, float]] = {}
    matchups: Dict[str, Dict[str, str]] = {}
    for r in (tt.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup", "")
        side = (r.get("side", "") or "").upper()
        if not m or not side: continue
        team_metrics[f"{m}|{side}"] = {
            "sf_gp": _safe(r.get("sf_gp") or r.get("team_sf_gp"), LEAGUE_SF_GP),
            "sa_gp": _safe(r.get("sa_gp") or r.get("opp_sa_gp"), LEAGUE_SF_GP),
            "team": r.get("team", ""),
        }
        matchups.setdefault(m, {})[side] = r.get("team", "")

    # SOG line by matchup (from props) for reference
    sog_line: Dict[str, float] = {}
    for r in (sog_total.get("rows") or []):
        if isinstance(r, dict):
            sog_line[r.get("matchup", "")] = _safe(r.get("line") or r.get("total"))

    rows: List[Dict[str, Any]] = []
    for m, sides in matchups.items():
        home = team_metrics.get(f"{m}|HOME")
        away = team_metrics.get(f"{m}|AWAY")
        if not home or not away: continue

        # Blended game SOG projection
        home_sog = (home["sf_gp"] + away["sa_gp"]) / 2.0
        away_sog = (away["sf_gp"] + home["sa_gp"]) / 2.0
        game_sog = home_sog + away_sog

        # Goal pace
        game_goals = game_sog * LEAGUE_SHOOT_PCT

        line = sog_line.get(m, 0)
        lean = None
        if line > 0:
            if game_sog >= line + 1.5:
                lean = "SOG_OVER_LEAN"
            elif game_sog <= line - 1.5:
                lean = "SOG_UNDER_LEAN"
            else:
                lean = "NEUTRAL"

        rows.append({
            "matchup": m,
            "home_team": home["team"],
            "away_team": away["team"],
            "projected_home_sog": round(home_sog, 1),
            "projected_away_sog": round(away_sog, 1),
            "projected_game_sog": round(game_sog, 1),
            "projected_game_goals": round(game_goals, 2),
            "sog_line": line or None,
            "lean": lean,
        })

    rows.sort(key=lambda r: -r["projected_game_sog"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "method_note": "Pure-model NHL pace projection. game_sog = blended "
                       "(home_SF + away_SA)/2 + (away_SF + home_SA)/2. "
                       "game_goals = game_sog * league shooting% (9.5%). "
                       "SOG_OVER/UNDER leans when proj is >=1.5 off the line.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-pace] {o['n_games']} games projected -> {OUT}")
