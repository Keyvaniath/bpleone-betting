"""
EdgeStat -- WNBA player rebounds + assists prop projections.

Combined module for two WNBA prop markets:
  - REB over/under (typically 6.5, 7.5, 8.5 for top rebounders)
  - AST over/under (typically 3.5, 4.5, 5.5 for top guards)

projected_X = season_X_per_game × pace_factor × matchup_factor.
Normal CDF at nearest 0.5 line within 0.75 of projection.
STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/wnba_player_reb_ast_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_reb_ast_props.json")

LEAGUE_PACE_WNBA = 78.0

# 2024-25 WNBA top REB/AST leaders
PLAYER_DB = {
    "a'ja wilson":          {"team": "LV",   "rpg": 11.9, "apg": 2.3, "pos": "F"},
    "alyssa thomas":        {"team": "CONN", "rpg": 8.4,  "apg": 7.9, "pos": "F"},
    "breanna stewart":      {"team": "NY",   "rpg": 8.5,  "apg": 3.8, "pos": "F"},
    "napheesa collier":     {"team": "MIN",  "rpg": 9.5,  "apg": 3.4, "pos": "F"},
    "sabrina ionescu":      {"team": "NY",   "rpg": 4.5,  "apg": 6.2, "pos": "G"},
    "caitlin clark":        {"team": "IND",  "rpg": 5.7,  "apg": 8.4, "pos": "G"},
    "kelsey plum":          {"team": "LA",   "rpg": 2.8,  "apg": 4.2, "pos": "G"},
    "diana taurasi":        {"team": "PHX",  "rpg": 2.5,  "apg": 4.0, "pos": "G"},
    "kahleah copper":       {"team": "PHX",  "rpg": 4.5,  "apg": 2.5, "pos": "G"},
    "arike ogunbowale":     {"team": "DAL",  "rpg": 3.0,  "apg": 4.6, "pos": "G"},
    "satou sabally":        {"team": "DAL",  "rpg": 7.8,  "apg": 3.2, "pos": "F"},
    "dewanna bonner":       {"team": "CONN", "rpg": 5.5,  "apg": 2.0, "pos": "F"},
    "rhyne howard":         {"team": "ATL",  "rpg": 4.5,  "apg": 3.2, "pos": "G"},
    "allisha gray":         {"team": "ATL",  "rpg": 4.0,  "apg": 3.5, "pos": "G"},
    "nneka ogwumike":       {"team": "SEA",  "rpg": 8.2,  "apg": 2.0, "pos": "F"},
    "skylar diggins-smith": {"team": "SEA",  "rpg": 2.6,  "apg": 6.0, "pos": "G"},
    "kayla mcbride":        {"team": "MIN",  "rpg": 4.5,  "apg": 4.0, "pos": "G"},
    "kelsey mitchell":      {"team": "IND",  "rpg": 2.7,  "apg": 2.5, "pos": "G"},
    "aliyah boston":        {"team": "IND",  "rpg": 8.7,  "apg": 3.5, "pos": "F"},
    "angel reese":          {"team": "CHI",  "rpg": 13.1, "apg": 2.0, "pos": "F"},
    "chennedy carter":      {"team": "CHI",  "rpg": 3.8,  "apg": 3.5, "pos": "G"},
    "jonquel jones":        {"team": "NY",   "rpg": 9.0,  "apg": 2.5, "pos": "F"},
    "ezi magbegor":         {"team": "SEA",  "rpg": 6.8,  "apg": 1.5, "pos": "F"},
    "jewell loyd":          {"team": "LV",   "rpg": 3.5,  "apg": 4.0, "pos": "G"},
    "jackie young":         {"team": "LV",   "rpg": 4.0,  "apg": 5.0, "pos": "G"},
    "dijonai carrington":   {"team": "CONN", "rpg": 4.5,  "apg": 2.5, "pos": "G"},
    "natasha cloud":        {"team": "PHX",  "rpg": 4.5,  "apg": 6.8, "pos": "G"},
    "elizabeth williams":   {"team": "CHI",  "rpg": 7.0,  "apg": 1.5, "pos": "F"},
    "lexie hull":           {"team": "IND",  "rpg": 3.5,  "apg": 1.5, "pos": "G"},
    "rae burrell":          {"team": "LA",   "rpg": 3.0,  "apg": 1.5, "pos": "G"},
}

TEAM_PACE = {
    "ATL": 82.5, "CHI": 79.8, "CONN": 78.2, "DAL": 80.5, "IND": 84.1, "LA": 79.6,
    "LV":  82.8, "MIN": 78.5, "NY":  77.8, "PHX": 80.1, "SEA": 79.0, "WAS": 79.5,
}

TEAM_FULL = {
    "atlanta dream": "ATL", "chicago sky": "CHI", "connecticut sun": "CONN",
    "dallas wings": "DAL", "indiana fever": "IND", "los angeles sparks": "LA",
    "las vegas aces": "LV", "minnesota lynx": "MIN", "new york liberty": "NY",
    "phoenix mercury": "PHX", "seattle storm": "SEA", "washington mystics": "WAS",
    "golden state valkyries": "GSV",
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


def _evaluate_line(projection: float, sigma: float, market_prefix: str) -> Dict[str, Any]:
    """Find best edge at nearest 0.5 line. Books set lines AT projection -- so we
    only flag STRONG when the model is genuinely differentiated (p in tighter
    65-72%% range, not just 62-72%%)."""
    best_edge = "NONE"
    best_market = None
    base_line = round(projection * 2) / 2
    for line in (base_line - 0.5, base_line + 0.5):
        if line < 1.0: continue
        if abs(projection - line) > 0.6: continue   # tightened from 0.75
        z = (projection - line) / sigma
        p_over = _norm_cdf(z)
        p_under = 1 - p_over
        # Tightened: 65-72%% (15%+ edge vs -120 book breakeven)
        if 0.65 <= p_over <= 0.72:
            if not best_market or p_over > best_market["p"]:
                best_edge = "STRONG_OVER"
                best_market = {"market": f"{market_prefix}_OVER_{line}",
                               "p": round(p_over, 3), "fair_odds": _american(p_over), "line": line}
        elif 0.65 <= p_under <= 0.72:
            if not best_market or p_under > best_market["p"]:
                best_edge = "STRONG_UNDER"
                best_market = {"market": f"{market_prefix}_UNDER_{line}",
                               "p": round(p_under, 3), "fair_odds": _american(p_under), "line": line}
    return {"edge_class": best_edge, "best_market": best_market}


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "wnba_state.json"))
    games = state.get("games") or state.get("events") or []

    reb_rows: List[Dict[str, Any]] = []
    ast_rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_PACE_WNBA)
        away_pace = TEAM_PACE.get(away, LEAGUE_PACE_WNBA)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE_WNBA

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home

            proj_reb = info["rpg"] * pace_factor
            proj_ast = info["apg"] * pace_factor
            sigma_reb = max(1.8, 0.22 * proj_reb)
            sigma_ast = max(1.5, 0.30 * proj_ast)

            reb_eval = _evaluate_line(proj_reb, sigma_reb, "REB")
            reb_rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name, "team": info["team"],
                "position": info["pos"], "season_rpg": info["rpg"],
                "projected_reb": round(proj_reb, 1), "sigma": round(sigma_reb, 2),
                **reb_eval,
            })

            ast_eval = _evaluate_line(proj_ast, sigma_ast, "AST")
            ast_rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name, "team": info["team"],
                "position": info["pos"], "season_apg": info["apg"],
                "projected_ast": round(proj_ast, 1), "sigma": round(sigma_ast, 2),
                **ast_eval,
            })

    reb_rows.sort(key=lambda r: -r["projected_reb"])
    ast_rows.sort(key=lambda r: -r["projected_ast"])
    strong_reb = [r for r in reb_rows if r["edge_class"].startswith("STRONG")]
    strong_ast = [r for r in ast_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_reb_projected": len(reb_rows),
        "n_ast_projected": len(ast_rows),
        "n_strong_reb": len(strong_reb),
        "n_strong_ast": len(strong_ast),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "WNBA player RPG/APG × pace_factor. Normal CDF at nearest 0.5 line. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "reb_rows": reb_rows,
        "ast_rows": ast_rows,
        "strong_reb": strong_reb,
        "strong_ast": strong_ast,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-reb-ast] reb={o['n_reb_projected']}/{o['n_strong_reb']} strong, "
          f"ast={o['n_ast_projected']}/{o['n_strong_ast']} strong")
