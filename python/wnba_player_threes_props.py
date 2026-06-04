"""
EdgeStat -- WNBA player 3-pointers made (3PM) prop projections.

Per-player projected 3PM = season_3pm * pace_factor * opp_3p_defense.
Poisson distribution at typical 0.5 lines.
WNBA games are 40 min (vs 48 NBA), pace ~80 possessions.
Common book lines: 0.5, 1.5, 2.5, 3.5 for top shooters.
STRONG when 10%+ edge vs -120 book breakeven (54.5%).

Output: data/wnba_player_threes_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_threes_props.json")

LEAGUE_PACE = 80.5  # WNBA league avg possessions/game

# 2024 WNBA top 3-point shooters (3PM per game)
PLAYER_DB = {
    "kelsey plum":            {"team": "LVA", "tpm": 2.5},
    "sabrina ionescu":        {"team": "NYL", "tpm": 3.1},
    "caitlin clark":          {"team": "IND", "tpm": 3.1},
    "kelsey mitchell":        {"team": "IND", "tpm": 2.5},
    "rhyne howard":           {"team": "ATL", "tpm": 2.8},
    "allisha gray":           {"team": "ATL", "tpm": 2.0},
    "arike ogunbowale":       {"team": "DAL", "tpm": 2.8},
    "satou sabally":          {"team": "DAL", "tpm": 2.0},
    "jewell loyd":            {"team": "SEA", "tpm": 2.2},
    "skylar diggins-smith":   {"team": "SEA", "tpm": 1.8},
    "kahleah copper":          {"team": "PHX", "tpm": 2.5},
    "diana taurasi":          {"team": "PHX", "tpm": 1.8},
    "courtney vandersloot":   {"team": "CHI", "tpm": 1.3},
    "marina mabrey":          {"team": "CHI", "tpm": 2.6},
    "diamond miller":         {"team": "MIN", "tpm": 1.5},
    "kayla mcbride":          {"team": "MIN", "tpm": 2.0},
    "courtney williams":      {"team": "MIN", "tpm": 1.6},
    "napheesa collier":       {"team": "MIN", "tpm": 0.9},
    "alyssa thomas":          {"team": "CON", "tpm": 0.3},
    "dijonai carrington":     {"team": "CON", "tpm": 1.2},
    "tiffany hayes":          {"team": "LVA", "tpm": 1.4},
    "jackie young":           {"team": "LVA", "tpm": 1.4},
    "chelsea gray":           {"team": "LVA", "tpm": 1.5},
    "aja wilson":             {"team": "LVA", "tpm": 0.4},
    "leonie fiebich":         {"team": "NYL", "tpm": 1.6},
    "kennedy burke":          {"team": "NYL", "tpm": 0.8},
    "natasha cloud":          {"team": "PHX", "tpm": 1.8},
    "azura stevens":          {"team": "LAS", "tpm": 1.0},
    "kelsey plum":            {"team": "LAS", "tpm": 2.5},  # traded
    "dearica hamby":          {"team": "LAS", "tpm": 0.8},
    "rickea jackson":         {"team": "LAS", "tpm": 1.4},
    "cameron brink":          {"team": "LAS", "tpm": 0.5},
    "lexie hull":             {"team": "IND", "tpm": 1.2},
    "nalyssa smith":          {"team": "IND", "tpm": 0.5},
    "ezi magbegor":           {"team": "SEA", "tpm": 0.4},
    "nneka ogwumike":         {"team": "SEA", "tpm": 0.6},
    "gabby williams":         {"team": "SEA", "tpm": 1.3},
    "brittney griner":        {"team": "ATL", "tpm": 0.0},
    "aliyah boston":          {"team": "IND", "tpm": 0.4},
    "angel reese":            {"team": "CHI", "tpm": 0.5},
}

# WNBA team pace (possessions/game)
TEAM_PACE = {
    "LVA": 82.0, "NYL": 80.5, "IND": 84.5, "ATL": 81.2, "DAL": 80.0,
    "SEA": 78.5, "PHX": 79.8, "CHI": 80.5, "MIN": 79.5, "CON": 78.0,
    "LAS": 81.5, "WAS": 79.5,
}

# WNBA per-team 3PA allowed per game. League avg ~10.5
TEAM_3P_DEFENSE = {
    "LVA": 10.5, "NYL": 9.8, "IND": 11.2, "ATL": 10.8, "DAL": 10.5,
    "SEA": 10.0, "PHX": 11.0, "CHI": 10.5, "MIN": 9.5, "CON": 9.8,
    "LAS": 11.5, "WAS": 11.2,
}

TEAM_FULL = {
    "las vegas aces": "LVA", "new york liberty": "NYL", "indiana fever": "IND",
    "atlanta dream": "ATL", "dallas wings": "DAL", "seattle storm": "SEA",
    "phoenix mercury": "PHX", "chicago sky": "CHI", "minnesota lynx": "MIN",
    "connecticut sun": "CON", "los angeles sparks": "LAS",
    "washington mystics": "WAS",
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
    state = _load(os.path.join(DATA_DIR, "wnba_state.json"))
    from nba_slate import upcoming_games  # shared slate gate (stale/future/non-imminent)
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
        home_def = TEAM_3P_DEFENSE.get(home, 10.5)
        away_def = TEAM_3P_DEFENSE.get(away, 10.5)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_def = away_def if is_home else home_def
            opp_def_factor = opp_def / 10.5

            # Real ESPN 3PM with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("wnba", player_name, "threes_per_game", fallback=info["tpm"], min_games=5)
                base_tpm = stat["value"]
                tpm_source = stat["source"]
            except Exception:
                base_tpm = info["tpm"]
                tpm_source = "fallback"
            projected_tpm = base_tpm * pace_factor * opp_def_factor

            # Only evaluate nearest 0.5 line within 0.75 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_tpm * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected_tpm - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, projected_tpm)
                p_under = 1 - p_over
                # STRONG bounds: 10%+ edge vs -120 book breakeven (54.5%)
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"3PM_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"3PM_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "game_date": g.get("game_date"),
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_tpm": base_tpm,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_3p_defense": opp_def,
                "opp_def_factor": round(opp_def_factor, 3),
                "projected_tpm": round(projected_tpm, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_tpm"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "WNBA player 3PM x pace x opp_3p_defense. Poisson at nearest 0.5 line. "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-3pm] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
