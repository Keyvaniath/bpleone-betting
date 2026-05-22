"""
EdgeStat -- NBA team total edge model.

Companion to mlb_team_total_edge. For each NBA game tonight, computes:
  - Expected team_pts via pace * efficiency
  - Compare to book team total (from market.team_total_home/away or implied)
  - Identify STRONG_OVER / STRONG_UNDER

Method:
  proj_team_pts = team_PPG * pace_factor * opp_defense_factor
                  + back_to_back_penalty - 0
                  + playoff_intensity (close games go deep)
  Bayesian shrink 35% toward book half-total.

  STRONG_OVER at edge >= 4.0 pts vs book
  STRONG_UNDER at edge <= -4.0 pts

Output: data/nba_team_total_edge.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_team_total_edge.json")

LEAGUE_PACE = 99.5
LEAGUE_DRTG = 115.8
LEAGUE_PPG_PER_TEAM = 113.0

# Team season PPG (top scorers' teams; supplement default 110)
TEAM_PPG = {
    "MEM": 120.5, "BOS": 119.2, "MIN": 117.5, "OKC": 116.8, "DEN": 116.5,
    "DAL": 116.0, "ATL": 115.5, "MIL": 115.2, "CLE": 115.0, "PHX": 114.7,
    "IND": 117.0, "LAL": 113.5, "GSW": 114.2, "NYK": 114.0, "PHI": 113.5,
    "SAC": 116.5, "ORL": 110.5, "BKN": 110.0, "POR": 109.5, "MIA": 110.5,
    "HOU": 112.0, "SAS": 110.8, "NOP": 112.5, "DET": 109.0, "TOR": 110.5,
    "UTA": 113.0, "CHA": 110.5, "CHI": 110.0, "WAS": 108.5, "LAC": 113.0,
}

TEAM_DRTG = {
    "MEM": 113.8, "WAS": 119.7, "IND": 113.6, "OKC": 107.0, "SAC": 117.4, "BOS": 111.4,
    "DEN": 115.9, "MIN": 110.9, "NYK": 112.5, "LAL": 114.0, "MIA": 113.0, "GSW": 113.8,
    "PHX": 115.4, "CLE": 112.0, "PHI": 113.0, "DAL": 113.6, "MIL": 113.4, "ATL": 116.0,
    "ORL": 109.2, "BKN": 115.6, "DET": 115.5, "CHA": 115.5, "TOR": 113.8, "POR": 115.5,
    "UTA": 117.5, "HOU": 110.0, "SAS": 115.0, "NOP": 114.0, "CHI": 115.6, "LAC": 110.5,
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}


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


def _abbr(name: str) -> str:
    if not name: return ""
    mapping = {
        "memphis grizzlies": "MEM", "washington wizards": "WAS", "indiana pacers": "IND",
        "oklahoma city thunder": "OKC", "sacramento kings": "SAC", "boston celtics": "BOS",
        "denver nuggets": "DEN", "minnesota timberwolves": "MIN", "new york knicks": "NYK",
        "los angeles lakers": "LAL", "miami heat": "MIA", "golden state warriors": "GSW",
        "phoenix suns": "PHX", "cleveland cavaliers": "CLE", "philadelphia 76ers": "PHI",
        "dallas mavericks": "DAL", "milwaukee bucks": "MIL", "atlanta hawks": "ATL",
        "orlando magic": "ORL", "brooklyn nets": "BKN", "detroit pistons": "DET",
        "charlotte hornets": "CHA", "toronto raptors": "TOR", "portland trail blazers": "POR",
        "utah jazz": "UTA", "houston rockets": "HOU", "san antonio spurs": "SAS",
        "new orleans pelicans": "NOP", "chicago bulls": "CHI", "los angeles clippers": "LAC",
    }
    return mapping.get(name.lower().strip(), name[:3].upper())


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        matchup = f"{away} @ {home}"
        is_playoff = "playoff" in (g.get("series_name") or "").lower() or bool(g.get("playoffs"))
        playoff_factor = 0.97 if is_playoff else 1.0  # playoff games typically slightly lower scoring

        # Game total from market (if available)
        market = g.get("market") or {}
        game_total = _safe(market.get("total"), 224.0)
        half_total = game_total / 2.0

        for side, opp_side in (("home", "away"), ("away", "home")):
            team = home if side == "home" else away
            opp = away if side == "home" else home

            ppg = TEAM_PPG.get(team, LEAGUE_PPG_PER_TEAM)
            opp_drtg = TEAM_DRTG.get(opp, LEAGUE_DRTG)
            team_pace = TEAM_PACE.get(team, LEAGUE_PACE)
            opp_pace = TEAM_PACE.get(opp, LEAGUE_PACE)
            game_pace = (team_pace + opp_pace) / 2.0

            pace_factor = game_pace / LEAGUE_PACE
            drtg_factor = opp_drtg / LEAGUE_DRTG

            proj_pts = ppg * pace_factor * drtg_factor * playoff_factor

            # Bayesian shrink 35% toward book half-total
            anchor_w = 0.35
            anchored = half_total * anchor_w + proj_pts * (1 - anchor_w)

            edge_pts = anchored - half_total

            if edge_pts >= 4.0:
                direction = "STRONG_OVER"
            elif edge_pts >= 1.5:
                direction = "LEAN_OVER"
            elif edge_pts <= -4.0:
                direction = "STRONG_UNDER"
            elif edge_pts <= -1.5:
                direction = "LEAN_UNDER"
            else:
                direction = "NEUTRAL"

            rows.append({
                "matchup": matchup,
                "side": side.upper(),
                "team": team,
                "opp": opp,
                "team_ppg": ppg,
                "opp_drtg": opp_drtg,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "drtg_factor": round(drtg_factor, 3),
                "is_playoff": is_playoff,
                "book_team_total": half_total,
                "model_proj_pts_raw": round(proj_pts, 1),
                "model_proj_pts_anchored": round(anchored, 1),
                "edge_pts": round(edge_pts, 2),
                "direction": direction,
            })

    rows.sort(key=lambda r: -abs(r["edge_pts"]))
    strong = [r for r in rows if r["direction"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "NBA team total = season_PPG * pace_factor * opp_DRtg_factor * "
                       "playoff_factor, Bayesian-shrunk 35% toward book half-total. "
                       "STRONG_OVER/UNDER at +/- 4.0 pts; LEAN at +/- 1.5 pts.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-tt] {o['n_team_sides']} team-sides, {o['n_strong_edges']} strong -> {OUT}")
