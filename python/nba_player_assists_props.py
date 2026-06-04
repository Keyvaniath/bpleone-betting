"""
EdgeStat -- NBA player assists (AST) prop projections.

Per-player projected AST = season_apg × pace_factor × usage_factor.
Normal CDF at nearest 0.5 line within 0.75 of projection. STRONG = 10%+
edge vs -120 book.

Output: data/nba_player_assists_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_assists_props.json")

LEAGUE_PACE = 99.5

# 2024-25 season top NBA AST leaders + team + position type
PLAYER_DB = {
    "tyrese haliburton":        {"team": "IND", "apg": 9.3, "pos": "PG"},
    "trae young":               {"team": "ATL", "apg": 11.2, "pos": "PG"},
    "luka doncic":              {"team": "LAL", "apg": 8.0, "pos": "PG"},
    "shai gilgeous-alexander":  {"team": "OKC", "apg": 6.2, "pos": "PG"},
    "lebron james":             {"team": "LAL", "apg": 8.2, "pos": "SF"},
    "nikola jokic":             {"team": "DEN", "apg": 10.0, "pos": "C"},
    "domantas sabonis":         {"team": "SAC", "apg": 8.0, "pos": "C"},
    "james harden":             {"team": "LAC", "apg": 8.5, "pos": "PG"},
    "jalen brunson":            {"team": "NYK", "apg": 7.3, "pos": "PG"},
    "stephen curry":            {"team": "GSW", "apg": 6.2, "pos": "PG"},
    "darius garland":           {"team": "CLE", "apg": 6.5, "pos": "PG"},
    "ja morant":                {"team": "MEM", "apg": 7.6, "pos": "PG"},
    "tyrese maxey":             {"team": "PHI", "apg": 6.0, "pos": "PG"},
    "scoot henderson":          {"team": "POR", "apg": 5.5, "pos": "PG"},
    "anfernee simons":          {"team": "POR", "apg": 4.6, "pos": "SG"},
    "cade cunningham":          {"team": "DET", "apg": 9.1, "pos": "PG"},
    "lamelo ball":              {"team": "CHA", "apg": 7.1, "pos": "PG"},
    "fred vanvleet":            {"team": "HOU", "apg": 8.1, "pos": "PG"},
    "jrue holiday":             {"team": "BOS", "apg": 4.5, "pos": "PG"},
    "derrick white":            {"team": "BOS", "apg": 4.5, "pos": "SG"},
    "jayson tatum":             {"team": "BOS", "apg": 5.8, "pos": "SF"},
    "anthony edwards":          {"team": "MIN", "apg": 4.5, "pos": "SG"},
    "mike conley":              {"team": "MIN", "apg": 5.8, "pos": "PG"},
    "devin booker":             {"team": "PHX", "apg": 6.5, "pos": "SG"},
    "kevin durant":             {"team": "PHX", "apg": 4.5, "pos": "SF"},
    "tre jones":                {"team": "CHI", "apg": 5.7, "pos": "PG"},
    "coby white":               {"team": "CHI", "apg": 4.6, "pos": "SG"},
    "alperen sengun":           {"team": "HOU", "apg": 4.9, "pos": "C"},
    "victor wembanyama":        {"team": "SAS", "apg": 3.7, "pos": "C"},
    "chris paul":               {"team": "SAS", "apg": 7.3, "pos": "PG"},
    "donovan mitchell":         {"team": "CLE", "apg": 5.0, "pos": "SG"},
    "kyrie irving":             {"team": "DAL", "apg": 4.7, "pos": "PG"},
    "spencer dinwiddie":        {"team": "DAL", "apg": 4.4, "pos": "PG"},
    "russell westbrook":        {"team": "DEN", "apg": 6.5, "pos": "PG"},
    "jamal murray":             {"team": "DEN", "apg": 6.5, "pos": "PG"},
}

TEAM_PACE = {
    "MEM": 103.9, "WAS": 103.0, "IND": 102.8, "OKC": 100.1, "SAC": 102.3, "BOS": 99.2,
    "DEN": 96.5, "MIN": 98.2, "NYK": 97.5, "LAL": 99.6, "MIA": 98.9, "GSW": 101.5,
    "PHX": 100.4, "CLE": 100.5, "PHI": 99.1, "DAL": 98.5, "MIL": 98.8, "ATL": 101.6,
    "ORL": 98.6, "BKN": 97.9, "DET": 99.7, "CHA": 100.8, "TOR": 99.1, "POR": 101.2,
    "UTA": 101.0, "HOU": 97.6, "SAS": 99.8, "NOP": 98.3, "CHI": 99.5, "LAC": 99.0,
}

# Full team name -> abbrev (nba_state.json uses full names)
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

            # Prefer REAL ESPN APG with hardcoded fallback (2026-05-21 data integrity)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nba", player_name, "ast_per_game",
                                       fallback=info["apg"], min_games=5)
                base_apg = stat["value"]
                apg_source = stat["source"]
            except Exception:
                base_apg = info["apg"]
                apg_source = "fallback"
            projected_ast = base_apg * pace_factor
            # AST variance is higher than PTS (more spiky)
            sigma = max(2.0, 0.30 * projected_ast)

            # Only nearest line within 0.75 of projection (where books actually price)
            best_edge_class = "NONE"
            best_market = None
            base_line = round(projected_ast * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 1.5: continue
                if abs(projected_ast - line) > 0.75: continue
                z = (projected_ast - line) / sigma
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        best_edge_class = "STRONG_OVER"
                        best_market = {"market": f"AST_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        best_edge_class = "STRONG_UNDER"
                        best_market = {"market": f"AST_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "game_date": g.get("game_date"),
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "position": info["pos"],
                "season_apg": round(base_apg, 2),
                "apg_source": apg_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "projected_ast": round(projected_ast, 1),
                "sigma": round(sigma, 2),
                "edge_class": best_edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_ast"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NBA player APG × pace factor. Normal CDF at nearest 0.5 line. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-ast] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
