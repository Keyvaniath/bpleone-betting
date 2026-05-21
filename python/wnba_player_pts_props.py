"""
EdgeStat -- WNBA player points (PTS) prop projections.

Mirror of nba_player_points_props.py but for active WNBA games.

Approach:
  projected_pts = season_ppg × game_pace_factor × opp_DRtg_factor
  Normal CDF on lines around projection with sigma = max(3.5, 0.25 × proj).

Player pool (baked in, WNBA top scorers 2024-25). Updates seasonally.

Output: data/wnba_player_pts_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_pts_props.json")

LEAGUE_PACE_WNBA = 78.0
LEAGUE_DRTG_WNBA = 100.5

# 2024-25 WNBA top scorers
PLAYER_DB = {
    "a'ja wilson":             {"team": "LV",  "ppg": 27.3, "usage": 0.33},
    "caitlin clark":           {"team": "IND", "ppg": 19.2, "usage": 0.28},
    "breanna stewart":         {"team": "NY",  "ppg": 20.4, "usage": 0.30},
    "napheesa collier":        {"team": "MIN", "ppg": 20.4, "usage": 0.28},
    "kelsey plum":             {"team": "LA",  "ppg": 17.8, "usage": 0.27},
    "diana taurasi":           {"team": "PHX", "ppg": 14.5, "usage": 0.24},
    "kahleah copper":          {"team": "PHX", "ppg": 19.0, "usage": 0.26},
    "arike ogunbowale":        {"team": "DAL", "ppg": 22.0, "usage": 0.29},
    "satou sabally":           {"team": "DAL", "ppg": 18.4, "usage": 0.27},
    "alyssa thomas":           {"team": "CONN", "ppg": 12.5, "usage": 0.22},
    "dewanna bonner":          {"team": "CONN", "ppg": 13.5, "usage": 0.23},
    "sabrina ionescu":         {"team": "NY",  "ppg": 18.5, "usage": 0.27},
    "jonquel jones":           {"team": "NY",  "ppg": 14.0, "usage": 0.22},
    "rhyne howard":            {"team": "ATL", "ppg": 18.0, "usage": 0.26},
    "allisha gray":            {"team": "ATL", "ppg": 18.0, "usage": 0.25},
    "nneka ogwumike":          {"team": "SEA", "ppg": 14.0, "usage": 0.23},
    "skylar diggins-smith":    {"team": "SEA", "ppg": 12.6, "usage": 0.22},
    "kayla mcbride":           {"team": "MIN", "ppg": 13.2, "usage": 0.22},
    "kelsey mitchell":         {"team": "IND", "ppg": 19.1, "usage": 0.27},
    "aliyah boston":           {"team": "IND", "ppg": 14.0, "usage": 0.22},
    "angel reese":             {"team": "CHI", "ppg": 13.6, "usage": 0.24},
    "chennedy carter":         {"team": "CHI", "ppg": 17.5, "usage": 0.27},
    "ezi magbegor":            {"team": "SEA", "ppg": 14.2, "usage": 0.23},
    "jewell loyd":             {"team": "LV",  "ppg": 18.0, "usage": 0.26},
    "elizabeth williams":      {"team": "CHI", "ppg": 11.0, "usage": 0.20},
    "lexie hull":              {"team": "IND", "ppg": 9.5,  "usage": 0.19},
    "dijonai carrington":      {"team": "CONN", "ppg": 12.5, "usage": 0.22},
    "natasha cloud":           {"team": "PHX", "ppg": 11.0, "usage": 0.20},
    "jackie young":            {"team": "LV",  "ppg": 17.0, "usage": 0.24},
    "rae burrell":             {"team": "LA",  "ppg": 10.5, "usage": 0.20},
}

# Team pace + DRtg
TEAM_PACE = {
    "ATL": 82.5, "CHI": 79.8, "CONN": 78.2, "DAL": 80.5, "IND": 84.1, "LA": 79.6,
    "LV":  82.8, "MIN": 78.5, "NY":  77.8, "PHX": 80.1, "SEA": 79.0, "WAS": 79.5,
}
TEAM_DRTG = {
    "ATL": 102.0, "CHI": 104.5, "CONN": 95.5, "DAL": 103.2, "IND": 105.0, "LA": 103.8,
    "LV":  96.8,  "MIN": 95.2,  "NY": 96.0,   "PHX": 100.5, "SEA": 99.0,  "WAS": 105.8,
}

# Team full name -> abbrev (ESPN wnba_state uses "Las Vegas Aces" etc.)
TEAM_FULL = {
    "atlanta dream": "ATL", "chicago sky": "CHI", "connecticut sun": "CONN",
    "dallas wings": "DAL", "indiana fever": "IND", "los angeles sparks": "LA",
    "las vegas aces": "LV", "minnesota lynx": "MIN", "new york liberty": "NY",
    "phoenix mercury": "PHX", "seattle storm": "SEA", "washington mystics": "WAS",
    "golden state valkyries": "GSV",  # 2025 expansion
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _abbr(name: str) -> str:
    if not name: return ""
    return TEAM_FULL.get(name.lower().strip(), name[:3].upper())


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "wnba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE_WNBA)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE_WNBA)
        home_drtg = TEAM_DRTG.get(home, LEAGUE_DRTG_WNBA)
        away_drtg = TEAM_DRTG.get(away, LEAGUE_DRTG_WNBA)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE_WNBA

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_drtg = away_drtg if is_home else home_drtg
            matchup_factor = opp_drtg / LEAGUE_DRTG_WNBA

            # Real ESPN PPG with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("wnba", player_name, "pts_per_game", fallback=info["ppg"], min_games=5)
                base_ppg = stat["value"]
                ppg_source = stat["source"]
            except Exception:
                base_ppg = info["ppg"]
                ppg_source = "fallback"
            projected_pts = base_ppg * pace_factor * matchup_factor
            sigma = max(3.5, 0.25 * projected_pts)

            # Books set the line at or very near projected_pts. Only evaluate the
            # nearest 0.5 line above and below (within 0.75 of projection).
            best_edge_class = "NONE"
            best_market = None
            base_line = round(projected_pts * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 5: continue
                if abs(projected_pts - line) > 0.75: continue
                z = (projected_pts - line) / sigma
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        best_edge_class = "STRONG_OVER"
                        best_market = {"market": f"PTS_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        best_edge_class = "STRONG_UNDER"
                        best_market = {"market": f"PTS_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_ppg": base_ppg,
                "usage_rate": info["usage"],
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_drtg": opp_drtg,
                "matchup_factor": round(matchup_factor, 3),
                "projected_pts": round(projected_pts, 1),
                "sigma": round(sigma, 2),
                "edge_class": best_edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_pts"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "WNBA player PPG × pace × opp_DRtg factor. Normal CDF. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-pts] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
