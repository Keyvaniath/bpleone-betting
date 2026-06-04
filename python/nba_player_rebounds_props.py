"""
EdgeStat -- NBA player rebounds (REB) prop projections.

Per-player projected REB = season_rpg × game_pace_factor × opp_rebound_rate.
Normal CDF at nearest 0.5 line within 0.75 of projection. STRONG = 10%+
edge vs -120 book (p in [0.62, 0.72]).

Output: data/nba_player_rebounds_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_rebounds_props.json")

LEAGUE_PACE = 99.5

# 2024-25 NBA top rebounders (top centers/forwards)
PLAYER_DB = {
    "nikola jokic":             {"team": "DEN", "rpg": 13.7},
    "domantas sabonis":         {"team": "SAC", "rpg": 12.5},
    "rudy gobert":              {"team": "MIN", "rpg": 12.0},
    "anthony davis":            {"team": "LAL", "rpg": 12.8},
    "giannis antetokounmpo":    {"team": "MIL", "rpg": 11.7},
    "victor wembanyama":        {"team": "SAS", "rpg": 11.5},
    "alperen sengun":           {"team": "HOU", "rpg": 9.5},
    "karl-anthony towns":       {"team": "NYK", "rpg": 12.5},
    "jaren jackson jr":         {"team": "MEM", "rpg": 5.5},
    "joel embiid":              {"team": "PHI", "rpg": 11.5},
    "ivica zubac":              {"team": "LAC", "rpg": 12.3},
    "nikola vucevic":           {"team": "CHI", "rpg": 10.5},
    "evan mobley":              {"team": "CLE", "rpg": 9.5},
    "jarrett allen":            {"team": "CLE", "rpg": 9.7},
    "kristaps porzingis":       {"team": "BOS", "rpg": 7.5},
    "myles turner":             {"team": "IND", "rpg": 7.0},
    "deandre ayton":            {"team": "POR", "rpg": 10.5},
    "jusuf nurkic":             {"team": "PHX", "rpg": 9.0},
    "naz reid":                 {"team": "MIN", "rpg": 6.5},
    "kelly olynyk":             {"team": "NOP", "rpg": 5.5},
    "draymond green":           {"team": "GSW", "rpg": 6.5},
    "chet holmgren":            {"team": "OKC", "rpg": 7.9},
    "isaiah hartenstein":       {"team": "OKC", "rpg": 11.0},
    "scottie barnes":           {"team": "TOR", "rpg": 7.4},
    "paolo banchero":           {"team": "ORL", "rpg": 7.0},
    "luka doncic":              {"team": "LAL", "rpg": 8.5},
    "lebron james":             {"team": "LAL", "rpg": 7.3},
    "jayson tatum":             {"team": "BOS", "rpg": 8.7},
    "jaylen brown":             {"team": "BOS", "rpg": 6.5},
    "pascal siakam":            {"team": "IND", "rpg": 6.3},
    "zach edey":                {"team": "MEM", "rpg": 8.5},
    "walker kessler":           {"team": "UTA", "rpg": 12.0},
    "lauri markkanen":          {"team": "UTA", "rpg": 6.5},
    "shai gilgeous-alexander":  {"team": "OKC", "rpg": 5.0},
    "anthony edwards":          {"team": "MIN", "rpg": 5.5},
    "julius randle":            {"team": "MIN", "rpg": 7.1},
    "lamelo ball":              {"team": "CHA", "rpg": 5.3},
    "darius garland":           {"team": "CLE", "rpg": 2.7},
    "jonathan kuminga":         {"team": "GSW", "rpg": 5.0},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

TEAM_FULL = {
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


def _abbr(name: str) -> str:
    if not name: return ""
    return TEAM_FULL.get(name.lower().strip(), name[:3].upper())


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


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
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    from nba_slate import upcoming_games  # gate stale/future/non-imminent slate
    games = upcoming_games(state)

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home

            # Prefer REAL ESPN RPG with hardcoded fallback (2026-05-21 data integrity)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nba", player_name, "reb_per_game",
                                       fallback=info["rpg"], min_games=5)
                base_rpg = stat["value"]
                rpg_source = stat["source"]
            except Exception:
                base_rpg = info["rpg"]
                rpg_source = "fallback"
            projected_reb = base_rpg * pace_factor
            # Rebounds variance is moderate (sigma = 22%% of projected, but min 1.8)
            sigma = max(1.8, 0.22 * projected_reb)

            best_edge_class = "NONE"
            best_market = None
            base_line = round(projected_reb * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 2.0: continue
                if abs(projected_reb - line) > 0.75: continue
                z = (projected_reb - line) / sigma
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        best_edge_class = "STRONG_OVER"
                        best_market = {"market": f"REB_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        best_edge_class = "STRONG_UNDER"
                        best_market = {"market": f"REB_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "game_date": g.get("game_date"),
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_rpg": round(base_rpg, 2),
                "rpg_source": rpg_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "projected_reb": round(projected_reb, 1),
                "sigma": round(sigma, 2),
                "edge_class": best_edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_reb"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NBA player RPG × pace factor. Normal CDF at nearest 0.5 line. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-reb] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
