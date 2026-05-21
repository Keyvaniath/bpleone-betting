"""
EdgeStat -- NBA player free-throw attempts (FTA) prop projections.

Common DK lines: 4.5, 5.5, 6.5, 7.5, 8.5 FTA (mostly for stars who draw fouls).
Top FT generators: SGA, Embiid, Trae, Giannis, KD, Booker, Luka, Brunson.

Method:
  expected_FTA = season_fta * pace_factor * opp_foul_rate_factor
  Poisson at nearest 0.5 line within 1.0 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nba_player_ft_attempts_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_ft_attempts_props.json")

LEAGUE_PACE = 99.5
LEAGUE_FT_RATE = 21.5  # NBA avg team FT attempts per game

# 2024-25 NBA top FTA-per-game players
PLAYER_DB = {
    "shai gilgeous-alexander":  {"team": "OKC", "fta": 8.5},
    "giannis antetokounmpo":    {"team": "MIL", "fta": 9.0},
    "joel embiid":              {"team": "PHI", "fta": 9.2},
    "luka doncic":              {"team": "LAL", "fta": 7.5},
    "trae young":               {"team": "ATL", "fta": 7.0},
    "kevin durant":             {"team": "PHX", "fta": 6.5},
    "devin booker":             {"team": "PHX", "fta": 6.0},
    "jalen brunson":            {"team": "NYK", "fta": 5.5},
    "victor wembanyama":        {"team": "SAS", "fta": 6.5},
    "anthony edwards":          {"team": "MIN", "fta": 5.5},
    "lebron james":             {"team": "LAL", "fta": 5.0},
    "anthony davis":            {"team": "LAL", "fta": 7.5},
    "donovan mitchell":         {"team": "CLE", "fta": 5.0},
    "jayson tatum":             {"team": "BOS", "fta": 7.0},
    "jaylen brown":             {"team": "BOS", "fta": 4.5},
    "tyrese maxey":             {"team": "PHI", "fta": 5.0},
    "damian lillard":           {"team": "MIL", "fta": 6.0},
    "stephen curry":            {"team": "GSW", "fta": 4.5},
    "ja morant":                {"team": "MEM", "fta": 6.5},
    "zion williamson":          {"team": "NOP", "fta": 7.0},
    "kyrie irving":             {"team": "DAL", "fta": 4.5},
    "paolo banchero":           {"team": "ORL", "fta": 7.5},
    "franz wagner":             {"team": "ORL", "fta": 5.5},
    "deaaron fox":              {"team": "SAC", "fta": 5.5},
    "domantas sabonis":         {"team": "SAC", "fta": 5.0},
    "demar derozan":            {"team": "SAC", "fta": 4.8},
    "cade cunningham":          {"team": "DET", "fta": 6.0},
    "lamelo ball":              {"team": "CHA", "fta": 5.0},
    "alperen sengun":           {"team": "HOU", "fta": 5.5},
    "jalen green":              {"team": "HOU", "fta": 4.5},
    "scottie barnes":           {"team": "TOR", "fta": 4.0},
    "rj barrett":               {"team": "TOR", "fta": 5.0},
    "lauri markkanen":          {"team": "UTA", "fta": 4.5},
    "nikola jokic":             {"team": "DEN", "fta": 6.5},
    "jamal murray":             {"team": "DEN", "fta": 4.0},
    "jaren jackson jr":         {"team": "MEM", "fta": 5.5},
    "karl-anthony towns":       {"team": "NYK", "fta": 5.0},
    "pascal siakam":            {"team": "IND", "fta": 4.5},
    "tyrese haliburton":        {"team": "IND", "fta": 3.0},
    "paul george":              {"team": "PHI", "fta": 4.5},
    "kawhi leonard":            {"team": "LAC", "fta": 5.0},
    "james harden":             {"team": "LAC", "fta": 6.0},
    "norman powell":            {"team": "LAC", "fta": 4.0},
    "chet holmgren":            {"team": "OKC", "fta": 4.0},
    "jalen williams":           {"team": "OKC", "fta": 4.0},
    "darius garland":           {"team": "CLE", "fta": 3.5},
    "jaylen wells":             {"team": "MEM", "fta": 3.0},
    "brandon miller":           {"team": "CHA", "fta": 3.5},
    "evan mobley":              {"team": "CLE", "fta": 4.0},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

# Per-team FT attempts allowed per game (foul rate proxy). League avg ~21.5
# Teams that foul more = opponent gets more FTAs
TEAM_FT_ALLOWED = {
    "DET": 24.0, "UTA": 23.5, "POR": 23.0, "WAS": 23.0, "BKN": 22.5, "CHA": 22.5,
    "PHI": 22.0, "ATL": 22.0, "CHI": 21.5, "TOR": 22.0, "LAL": 21.0, "PHX": 21.0,
    "SAC": 21.5, "DAL": 21.5, "MIL": 21.0, "MIA": 21.5, "NOP": 22.0, "MIN": 19.5,
    "DEN": 20.0, "BOS": 19.5, "OKC": 19.5, "NYK": 19.5, "CLE": 20.0, "ORL": 21.0,
    "MEM": 21.5, "IND": 21.0, "HOU": 22.0, "GSW": 21.0, "LAC": 20.5, "SAS": 21.5,
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
        home_ft_allowed = TEAM_FT_ALLOWED.get(home, LEAGUE_FT_RATE)
        away_ft_allowed = TEAM_FT_ALLOWED.get(away, LEAGUE_FT_RATE)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_ft_allowed = away_ft_allowed if is_home else home_ft_allowed
            opp_foul_factor = opp_ft_allowed / LEAGUE_FT_RATE

            # Real ESPN FTA/game with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nba", player_name, "fta_per_game", fallback=info["fta"], min_games=5)
                base_fta = stat["value"]
                fta_source = stat["source"]
            except Exception:
                base_fta = info["fta"]
                fta_source = "fallback"
            projected_fta = base_fta * pace_factor * opp_foul_factor

            # Only evaluate nearest 0.5 line within 1.0 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_fta * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected_fta - line) > 1.0: continue
                p_over = _poisson_at_least(int(line) + 1, projected_fta)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"FTA_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"FTA_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_fta": round(base_fta, 2),
                "fta_source": fta_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_ft_allowed": opp_ft_allowed,
                "opp_foul_factor": round(opp_foul_factor, 3),
                "projected_fta": round(projected_fta, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_fta"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NBA player FTA x pace x opp_foul_rate. Poisson at nearest 0.5 line "
                       "within 1.0 of projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-fta] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
