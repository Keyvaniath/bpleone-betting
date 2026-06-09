"""
EdgeStat -- WNBA player blocks + steals combined prop projections.

Common DK line: blocks+steals 1.5, 2.5, 3.5 combined.

Method:
  expected_BLK_STL = (season_bpg + season_spg) * pace_factor * opp_factor
  Poisson at nearest 0.5 line within 0.75 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/wnba_player_blocks_steals_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

from wnba_scoring_env import game_env_factor


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_blocks_steals_props.json")

LEAGUE_PACE = 80.5

# 2024 WNBA top defensive stat producers (BLK + STL per game)
PLAYER_DB = {
    "aja wilson":             {"team": "LVA", "bpg": 2.6, "spg": 1.8},
    "alanna smith":           {"team": "MIN", "bpg": 1.9, "spg": 1.1},
    "ezi magbegor":           {"team": "SEA", "bpg": 1.9, "spg": 0.8},
    "brittney griner":        {"team": "ATL", "bpg": 1.6, "spg": 0.6},
    "alyssa thomas":          {"team": "CON", "bpg": 0.8, "spg": 1.8},
    "napheesa collier":       {"team": "MIN", "bpg": 1.5, "spg": 1.8},
    "dijonai carrington":     {"team": "CON", "bpg": 0.4, "spg": 1.9},
    "kayla mcbride":          {"team": "MIN", "bpg": 0.3, "spg": 1.3},
    "kelsey plum":            {"team": "LAS", "bpg": 0.2, "spg": 1.4},
    "satou sabally":          {"team": "DAL", "bpg": 0.8, "spg": 1.0},
    "rhyne howard":           {"team": "ATL", "bpg": 0.4, "spg": 1.4},
    "natasha cloud":          {"team": "PHX", "bpg": 0.2, "spg": 1.6},
    "courtney williams":      {"team": "MIN", "bpg": 0.2, "spg": 1.5},
    "jewell loyd":            {"team": "SEA", "bpg": 0.2, "spg": 1.3},
    "skylar diggins-smith":   {"team": "SEA", "bpg": 0.2, "spg": 1.4},
    "caitlin clark":          {"team": "IND", "bpg": 0.5, "spg": 1.3},
    "kahleah copper":         {"team": "PHX", "bpg": 0.3, "spg": 1.2},
    "sabrina ionescu":        {"team": "NYL", "bpg": 0.3, "spg": 1.1},
    "jackie young":           {"team": "LVA", "bpg": 0.3, "spg": 1.2},
    "chelsea gray":           {"team": "LVA", "bpg": 0.3, "spg": 1.1},
    "arike ogunbowale":       {"team": "DAL", "bpg": 0.3, "spg": 1.0},
    "kelsey mitchell":        {"team": "IND", "bpg": 0.2, "spg": 0.9},
    "diamond miller":         {"team": "MIN", "bpg": 0.5, "spg": 0.9},
    "allisha gray":           {"team": "ATL", "bpg": 0.3, "spg": 1.1},
    "tiffany hayes":          {"team": "LVA", "bpg": 0.2, "spg": 1.0},
    "marina mabrey":          {"team": "CHI", "bpg": 0.3, "spg": 1.1},
    "kennedy burke":          {"team": "NYL", "bpg": 0.3, "spg": 0.9},
    "nneka ogwumike":         {"team": "SEA", "bpg": 0.6, "spg": 0.8},
    "gabby williams":         {"team": "SEA", "bpg": 0.5, "spg": 1.2},
    "aliyah boston":          {"team": "IND", "bpg": 1.3, "spg": 0.9},
    "angel reese":            {"team": "CHI", "bpg": 0.7, "spg": 1.4},
    "cameron brink":          {"team": "LAS", "bpg": 2.3, "spg": 0.6},
    "rickea jackson":         {"team": "LAS", "bpg": 0.4, "spg": 0.7},
    "azura stevens":          {"team": "LAS", "bpg": 1.2, "spg": 0.8},
    "lexie hull":             {"team": "IND", "bpg": 0.2, "spg": 1.1},
    "nalyssa smith":          {"team": "IND", "bpg": 0.5, "spg": 0.6},
    "courtney vandersloot":   {"team": "CHI", "bpg": 0.2, "spg": 1.2},
    "dearica hamby":          {"team": "LAS", "bpg": 0.6, "spg": 0.9},
    "elizabeth williams":     {"team": "CHI", "bpg": 1.6, "spg": 0.6},
    "olivia nelson-ododa":    {"team": "LVA", "bpg": 0.8, "spg": 0.6},
}

TEAM_PACE = {
    "LVA": 82.0, "NYL": 80.5, "IND": 84.5, "ATL": 81.2, "DAL": 80.0,
    "SEA": 78.5, "PHX": 79.8, "CHI": 80.5, "MIN": 79.5, "CON": 78.0,
    "LAS": 81.5, "WAS": 79.5,
}

# Opp turnover/missed-shot rate proxy (higher = more opportunities for blocks/steals)
TEAM_DEFENSIVE_OPPS = {
    "LVA": 1.00, "NYL": 0.95, "IND": 1.05, "ATL": 1.05, "DAL": 1.00,
    "SEA": 1.00, "PHX": 1.00, "CHI": 1.05, "MIN": 0.95, "CON": 0.95,
    "LAS": 1.05, "WAS": 1.05,
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
        home_opps = TEAM_DEFENSIVE_OPPS.get(home, 1.0)
        away_opps = TEAM_DEFENSIVE_OPPS.get(away, 1.0)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE
        env, _env = game_env_factor(g.get("home_team") or "", g.get("away_team") or "")
        pace_factor *= env

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_factor = away_opps if is_home else home_opps

            # Real ESPN blk+stl per game with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                _b = get_player_stat("wnba", player_name, "blk_per_game", fallback=info["bpg"], min_games=5)
                _s = get_player_stat("wnba", player_name, "stl_per_game", fallback=info["spg"], min_games=5)
                base_bpg = _b["value"]; bs_source = _b["source"]
                base_spg = _s["value"]
            except Exception:
                base_bpg = info["bpg"]; bs_source = "fallback"
                base_spg = info["spg"]
            base = base_bpg + base_spg
            projected = base * pace_factor * opp_factor

            edge_class = "NONE"
            best_market = None
            base_line = round(projected * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, projected)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"BLK_STL_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"BLK_STL_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "game_date": g.get("game_date"),
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_bpg": round(base_bpg, 2),
                "blk_stl_source": bs_source,
                "season_spg": round(base_spg, 2),
                "pace_factor": round(pace_factor, 3),
                "opp_factor": round(opp_factor, 3),
                "projected_blk_stl": round(projected, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_blk_stl"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "WNBA player BLK+STL combo x pace x opp_factor. Poisson at nearest 0.5 line "
                       "within 0.75. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-blkstl] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
