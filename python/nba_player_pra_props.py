"""
EdgeStat -- NBA player PRA (Points + Rebounds + Assists) combo prop.

Top-3 most-bet NBA prop. Common DK lines: 25.5, 30.5, 35.5, 40.5, 45.5 PRA.

Method:
  expected_PRA = (ppg + rpg + apg) * pace_factor * opp_def_factor
  sigma = max(7.0, 0.20 * expected_PRA)  # PRA = sum of 3 correlated -> wider variance
  Normal CDF for over/under at nearest 1.0 line within 4.0 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nba_player_pra_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_pra_props.json")

LEAGUE_PACE = 99.5
LEAGUE_DRTG = 115.8

# 2024-25 NBA top PRA producers: ppg + rpg + apg combined
PLAYER_DB = {
    "luka doncic":              {"team": "LAL", "ppg": 28.5, "rpg": 8.7, "apg": 8.2},
    "nikola jokic":             {"team": "DEN", "ppg": 29.5, "rpg": 12.5, "apg": 10.0},
    "giannis antetokounmpo":    {"team": "MIL", "ppg": 30.4, "rpg": 11.5, "apg": 6.5},
    "shai gilgeous-alexander":  {"team": "OKC", "ppg": 32.7, "rpg": 5.5, "apg": 6.4},
    "jayson tatum":             {"team": "BOS", "ppg": 26.8, "rpg": 8.7, "apg": 5.6},
    "anthony edwards":          {"team": "MIN", "ppg": 27.6, "rpg": 5.7, "apg": 4.5},
    "lebron james":             {"team": "LAL", "ppg": 25.0, "rpg": 8.0, "apg": 9.0},
    "tyrese haliburton":        {"team": "IND", "ppg": 18.6, "rpg": 3.5, "apg": 9.6},
    "trae young":               {"team": "ATL", "ppg": 22.0, "rpg": 3.0, "apg": 11.7},
    "victor wembanyama":        {"team": "SAS", "ppg": 24.3, "rpg": 11.0, "apg": 3.7},
    "lamelo ball":              {"team": "CHA", "ppg": 25.0, "rpg": 4.8, "apg": 7.6},
    "domantas sabonis":         {"team": "SAC", "ppg": 20.5, "rpg": 13.5, "apg": 6.0},
    "joel embiid":              {"team": "PHI", "ppg": 24.5, "rpg": 11.0, "apg": 4.0},
    "anthony davis":            {"team": "LAL", "ppg": 24.5, "rpg": 11.5, "apg": 3.5},
    "donovan mitchell":         {"team": "CLE", "ppg": 24.2, "rpg": 4.8, "apg": 4.5},
    "jalen brunson":            {"team": "NYK", "ppg": 26.0, "rpg": 3.5, "apg": 7.5},
    "kyrie irving":             {"team": "DAL", "ppg": 25.0, "rpg": 4.5, "apg": 5.0},
    "ja morant":                {"team": "MEM", "ppg": 23.0, "rpg": 4.0, "apg": 7.0},
    "paolo banchero":           {"team": "ORL", "ppg": 25.0, "rpg": 7.5, "apg": 4.8},
    "franz wagner":             {"team": "ORL", "ppg": 24.0, "rpg": 5.5, "apg": 5.4},
    "stephen curry":            {"team": "GSW", "ppg": 24.5, "rpg": 4.5, "apg": 6.0},
    "kevin durant":             {"team": "PHX", "ppg": 27.0, "rpg": 6.5, "apg": 4.5},
    "devin booker":             {"team": "PHX", "ppg": 25.4, "rpg": 4.0, "apg": 7.0},
    "damian lillard":           {"team": "MIL", "ppg": 24.5, "rpg": 4.5, "apg": 7.0},
    "tyrese maxey":             {"team": "PHI", "ppg": 26.0, "rpg": 3.5, "apg": 6.0},
    "cade cunningham":          {"team": "DET", "ppg": 24.5, "rpg": 6.0, "apg": 9.0},
    "darius garland":           {"team": "CLE", "ppg": 20.5, "rpg": 3.0, "apg": 6.5},
    "alperen sengun":           {"team": "HOU", "ppg": 19.0, "rpg": 9.5, "apg": 4.8},
    "scottie barnes":           {"team": "TOR", "ppg": 19.5, "rpg": 7.5, "apg": 6.5},
    "rj barrett":               {"team": "TOR", "ppg": 21.0, "rpg": 6.5, "apg": 5.5},
    "karl-anthony towns":       {"team": "NYK", "ppg": 21.8, "rpg": 12.5, "apg": 3.0},
    "pascal siakam":            {"team": "IND", "ppg": 20.2, "rpg": 7.0, "apg": 4.0},
    "jaylen brown":             {"team": "BOS", "ppg": 23.5, "rpg": 6.0, "apg": 4.5},
    "deaaron fox":              {"team": "SAC", "ppg": 25.0, "rpg": 4.5, "apg": 6.5},
    "demar derozan":            {"team": "SAC", "ppg": 21.8, "rpg": 4.5, "apg": 5.0},
    "zion williamson":          {"team": "NOP", "ppg": 22.5, "rpg": 7.0, "apg": 5.0},
    "lauri markkanen":          {"team": "UTA", "ppg": 22.5, "rpg": 7.5, "apg": 2.0},
    "jalen williams":           {"team": "OKC", "ppg": 21.5, "rpg": 5.5, "apg": 5.5},
    "chet holmgren":            {"team": "OKC", "ppg": 17.0, "rpg": 8.5, "apg": 2.5},
    "brandon miller":           {"team": "CHA", "ppg": 21.0, "rpg": 5.0, "apg": 3.0},
    "paul george":              {"team": "PHI", "ppg": 20.0, "rpg": 5.5, "apg": 4.0},
    "rudy gobert":              {"team": "MIN", "ppg": 12.0, "rpg": 12.0, "apg": 2.0},
    "jaren jackson jr":         {"team": "MEM", "ppg": 22.0, "rpg": 5.5, "apg": 1.7},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

TEAM_DRTG = {
    "OKC": 106.5, "BOS": 110.5, "MIN": 110.0, "ORL": 111.0, "CLE": 112.5, "MEM": 113.0,
    "NYK": 113.0, "DEN": 113.5, "MIA": 113.0, "PHI": 114.5, "DAL": 113.5, "LAL": 114.5,
    "PHX": 116.0, "GSW": 116.5, "MIL": 115.5, "IND": 117.0, "HOU": 113.5, "ATL": 117.5,
    "SAC": 117.0, "CHI": 117.0, "TOR": 117.5, "BKN": 118.0, "LAC": 113.0, "DET": 118.5,
    "POR": 119.0, "SAS": 118.0, "UTA": 120.0, "CHA": 119.5, "WAS": 122.5, "NOP": 117.0,
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


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _p_over(mean: float, sigma: float, line: float) -> float:
    """P(X > line) for X ~ Normal(mean, sigma)."""
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE)
        home_drtg = TEAM_DRTG.get(home, LEAGUE_DRTG)
        away_drtg = TEAM_DRTG.get(away, LEAGUE_DRTG)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_drtg = away_drtg if is_home else home_drtg
            opp_def_factor = opp_drtg / LEAGUE_DRTG

            # Real ESPN per-game stats with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                ppg = get_player_stat("nba", player_name, "pts_per_game", fallback=info["ppg"], min_games=5)
                rpg = get_player_stat("nba", player_name, "reb_per_game", fallback=info["rpg"], min_games=5)
                apg = get_player_stat("nba", player_name, "ast_per_game", fallback=info["apg"], min_games=5)
                pra_source = "real" if ppg["source"] == "real" else "fallback"
                base_pra = ppg["value"] + rpg["value"] + apg["value"]
            except Exception:
                base_pra = info["ppg"] + info["rpg"] + info["apg"]
                pra_source = "fallback"
            projected_pra = base_pra * pace_factor * opp_def_factor
            sigma = max(7.0, 0.20 * projected_pra)

            # Evaluate nearest 1.0 line within 4.0 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_pra) + 0.5
            for line_int in (base_line - 3, base_line - 2, base_line - 1, base_line, base_line + 1, base_line + 2, base_line + 3):
                line = line_int
                if line < 5.5 or line > 70.5: continue
                if abs(projected_pra - line) > 4.0: continue
                p_over = _p_over(projected_pra, sigma, line)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"PRA_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"PRA_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_pra": round(base_pra, 1),
                "pra_source": pra_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_drtg": opp_drtg,
                "opp_def_factor": round(opp_def_factor, 3),
                "projected_pra": round(projected_pra, 1),
                "sigma": round(sigma, 1),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_pra"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NBA player PRA = (ppg+rpg+apg) x pace x opp_def. Normal CDF at nearest 1.0 "
                       "line within 4.0 of projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pra] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
