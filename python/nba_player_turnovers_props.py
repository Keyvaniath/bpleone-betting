"""
EdgeStat -- NBA player turnovers (TO) prop projections.

Common DK lines: 2.5, 3.5, 4.5 turnovers (depending on usage/role).
High-usage point guards drive most turnover props (Doncic, Harden, Trae, etc.).

Method:
  projected_TO = season_TO_per_game * pace_factor * opp_TO_force_factor
  Poisson distribution -> P(over X.5)
  STRONG when 10%+ edge vs -120 book breakeven (54.5%), within nearest 0.5 line.

Output: data/nba_player_turnovers_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_turnovers_props.json")

LEAGUE_PACE = 99.5
LEAGUE_TO_FORCED = 13.5  # NBA league avg turnovers forced per game

# 2024-25 NBA top usage / turnover-prone players (TO per game)
PLAYER_DB = {
    "luka doncic":              {"team": "LAL", "tovg": 4.0},
    "trae young":               {"team": "ATL", "tovg": 4.4},
    "james harden":             {"team": "LAC", "tovg": 4.1},
    "lamelo ball":              {"team": "CHA", "tovg": 3.8},
    "ja morant":                {"team": "MEM", "tovg": 3.5},
    "shai gilgeous-alexander":  {"team": "OKC", "tovg": 2.4},
    "anthony edwards":          {"team": "MIN", "tovg": 3.5},
    "jayson tatum":             {"team": "BOS", "tovg": 2.6},
    "tyrese haliburton":        {"team": "IND", "tovg": 2.5},
    "joel embiid":              {"team": "PHI", "tovg": 3.6},
    "tyrese maxey":             {"team": "PHI", "tovg": 1.8},
    "donovan mitchell":         {"team": "CLE", "tovg": 2.6},
    "darius garland":           {"team": "CLE", "tovg": 3.0},
    "kyrie irving":             {"team": "DAL", "tovg": 2.0},
    "jaylen brown":             {"team": "BOS", "tovg": 2.8},
    "jrue holiday":             {"team": "BOS", "tovg": 1.7},
    "stephen curry":            {"team": "GSW", "tovg": 3.0},
    "jalen brunson":            {"team": "NYK", "tovg": 2.3},
    "devin booker":             {"team": "PHX", "tovg": 2.8},
    "kevin durant":             {"team": "PHX", "tovg": 3.4},
    "damian lillard":           {"team": "MIL", "tovg": 2.7},
    "giannis antetokounmpo":    {"team": "MIL", "tovg": 3.4},
    "lebron james":             {"team": "LAL", "tovg": 3.5},
    "anthony davis":            {"team": "LAL", "tovg": 2.1},
    "nikola jokic":             {"team": "DEN", "tovg": 3.0},
    "jamal murray":             {"team": "DEN", "tovg": 2.0},
    "karl-anthony towns":       {"team": "NYK", "tovg": 2.5},
    "cade cunningham":          {"team": "DET", "tovg": 3.5},
    "paolo banchero":           {"team": "ORL", "tovg": 3.4},
    "victor wembanyama":        {"team": "SAS", "tovg": 3.2},
    "chet holmgren":            {"team": "OKC", "tovg": 1.9},
    "jalen williams":           {"team": "OKC", "tovg": 2.4},
    "scottie barnes":           {"team": "TOR", "tovg": 2.8},
    "alperen sengun":           {"team": "HOU", "tovg": 3.0},
    "domantas sabonis":         {"team": "SAC", "tovg": 3.0},
    "deaaron fox":              {"team": "SAC", "tovg": 2.6},
    "zion williamson":          {"team": "NOP", "tovg": 3.0},
    "pascal siakam":            {"team": "IND", "tovg": 2.0},
    "franz wagner":             {"team": "ORL", "tovg": 2.4},
    "jaren jackson jr":         {"team": "MEM", "tovg": 1.7},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

# Defensive pressure: turnovers FORCED per game (league avg ~13.5).
# Higher = more pressure on opponent ball handlers.
TEAM_TO_FORCED = {
    "OKC": 16.5, "MIN": 14.2, "ORL": 14.0, "CLE": 13.5, "NYK": 13.0, "HOU": 14.5,
    "BOS": 13.0, "MEM": 13.8, "DEN": 12.8, "MIA": 13.5, "PHX": 13.0, "LAL": 13.2,
    "GSW": 13.0, "DAL": 12.5, "MIL": 12.7, "ATL": 13.5, "IND": 13.0, "SAC": 13.2,
    "TOR": 13.4, "DET": 13.0, "CHA": 13.5, "WAS": 12.5, "BKN": 13.0, "PHI": 13.2,
    "UTA": 13.5, "PHI": 13.5, "POR": 13.0, "LAC": 12.8, "NOP": 14.0, "SAS": 13.2,
    "CHI": 13.5,
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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


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
        home_force = TEAM_TO_FORCED.get(home, LEAGUE_TO_FORCED)
        away_force = TEAM_TO_FORCED.get(away, LEAGUE_TO_FORCED)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_force = away_force if is_home else home_force
            # Higher opp_force -> more turnovers caused
            opp_force_factor = opp_force / LEAGUE_TO_FORCED

            # Real ESPN TOV/game with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nba", player_name, "tov_per_game", fallback=info["tovg"], min_games=5)
                base_tov = stat["value"]
                tov_source = stat["source"]
            except Exception:
                base_tov = info["tovg"]
                tov_source = "fallback"
            projected_tov = base_tov * pace_factor * opp_force_factor

            # Only evaluate nearest 0.5 line within 0.75 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_tov * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected_tov - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, projected_tov)
                p_under = 1 - p_over
                # STRONG: 10%+ edge vs -120 (54.5% breakeven), capped at 72%
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"TOV_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"TOV_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "game_date": g.get("game_date"),
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_tovg": round(base_tov, 2),
                "tov_source": tov_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_to_force": opp_force,
                "opp_force_factor": round(opp_force_factor, 3),
                "projected_tov": round(projected_tov, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_tov"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NBA player TO x pace x opp_TO_force_factor. Poisson at nearest 0.5 line. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-tov] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
