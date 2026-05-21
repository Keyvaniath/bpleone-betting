"""
EdgeStat -- NBA player triple-double yes/no prop projections.

Rare event prop. Common DK lines:
  - Jokic: +180 to +300 (likely)
  - Luka: +400 to +700
  - LeBron, Westbrook: +500 to +900
  - Most stars: +2000 to +5000
  - Bench players: +50000+ (essentially impossible)

Method:
  P(triple-double) = P(10+ pts) * P(10+ reb) * P(10+ ast) * correlation_lift
  where each is a Poisson tail probability.

  Triple-double events are HEAVILY correlated. When a player approaches one,
  he keeps shooting/passing — correlation_lift ~1.4 captures this empirically
  (raw multiplication understates true rate by ~40%).

  STRONG_YES when our P(TD) >= 12% (vs typical +500 book = 16.7% breakeven
  for Jokic-tier, but +500 is too thin — surface only true outliers).
  STRONG_YES when our P(TD) >= 20% (vs +400 book = 20% breakeven).

Output: data/nba_triple_double_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_triple_double_props.json")

LEAGUE_PACE = 99.5
CORRELATION_LIFT = 1.4

# 2024-25 top NBA players with TD potential (ppg, rpg, apg)
PLAYER_DB = {
    "nikola jokic":             {"team": "DEN", "ppg": 29.5, "rpg": 12.5, "apg": 10.0},
    "luka doncic":              {"team": "LAL", "ppg": 28.5, "rpg": 8.7, "apg": 8.2},
    "lebron james":             {"team": "LAL", "ppg": 25.0, "rpg": 8.0, "apg": 9.0},
    "giannis antetokounmpo":    {"team": "MIL", "ppg": 30.4, "rpg": 11.5, "apg": 6.5},
    "trae young":               {"team": "ATL", "ppg": 22.0, "rpg": 3.0, "apg": 11.7},
    "tyrese haliburton":        {"team": "IND", "ppg": 18.6, "rpg": 3.5, "apg": 9.6},
    "domantas sabonis":         {"team": "SAC", "ppg": 20.5, "rpg": 13.5, "apg": 6.0},
    "victor wembanyama":        {"team": "SAS", "ppg": 24.3, "rpg": 11.0, "apg": 3.7},
    "joel embiid":              {"team": "PHI", "ppg": 24.5, "rpg": 11.0, "apg": 4.0},
    "anthony davis":            {"team": "LAL", "ppg": 24.5, "rpg": 11.5, "apg": 3.5},
    "lamelo ball":              {"team": "CHA", "ppg": 25.0, "rpg": 4.8, "apg": 7.6},
    "jayson tatum":             {"team": "BOS", "ppg": 26.8, "rpg": 8.7, "apg": 5.6},
    "shai gilgeous-alexander":  {"team": "OKC", "ppg": 32.7, "rpg": 5.5, "apg": 6.4},
    "cade cunningham":          {"team": "DET", "ppg": 24.5, "rpg": 6.0, "apg": 9.0},
    "ja morant":                {"team": "MEM", "ppg": 23.0, "rpg": 4.0, "apg": 7.0},
    "paolo banchero":           {"team": "ORL", "ppg": 25.0, "rpg": 7.5, "apg": 4.8},
    "anthony edwards":          {"team": "MIN", "ppg": 27.6, "rpg": 5.7, "apg": 4.5},
    "scottie barnes":           {"team": "TOR", "ppg": 19.5, "rpg": 7.5, "apg": 6.5},
    "alperen sengun":           {"team": "HOU", "ppg": 19.0, "rpg": 9.5, "apg": 4.8},
    "karl-anthony towns":       {"team": "NYK", "ppg": 21.8, "rpg": 12.5, "apg": 3.0},
    "franz wagner":             {"team": "ORL", "ppg": 24.0, "rpg": 5.5, "apg": 5.4},
    "deaaron fox":              {"team": "SAC", "ppg": 25.0, "rpg": 4.5, "apg": 6.5},
    "russell westbrook":        {"team": "DEN", "ppg": 14.0, "rpg": 5.5, "apg": 6.0},
    "draymond green":           {"team": "GSW", "ppg": 8.5, "rpg": 6.5, "apg": 6.0},
    "josh giddey":              {"team": "CHI", "ppg": 14.5, "rpg": 8.0, "apg": 7.5},
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


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _p_at_least_10(mean: float, sigma: float) -> float:
    """P(X >= 10) for X ~ Normal(mean, sigma) — i.e. game-stat threshold."""
    if sigma <= 0: return 1.0 if mean >= 10 else 0.0
    z = (9.5 - mean) / sigma
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
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_PACE

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home

            # Project each stat with pace adjustment
            proj_pts = info["ppg"] * pace_factor
            proj_reb = info["rpg"] * pace_factor
            proj_ast = info["apg"] * pace_factor

            # Sigma per stat (heuristic)
            sigma_pts = max(5.0, 0.22 * proj_pts)
            sigma_reb = max(2.5, 0.30 * proj_reb)
            sigma_ast = max(2.0, 0.35 * proj_ast)

            # P(>=10) for each
            p_pts_10 = _p_at_least_10(proj_pts, sigma_pts)
            p_reb_10 = _p_at_least_10(proj_reb, sigma_reb)
            p_ast_10 = _p_at_least_10(proj_ast, sigma_ast)

            # Raw independent product * correlation lift
            p_td_raw = p_pts_10 * p_reb_10 * p_ast_10
            p_td = min(0.60, p_td_raw * CORRELATION_LIFT)
            p_no_td = 1 - p_td

            edge_class = "NONE"
            best_market = None
            # STRONG_YES when p >= 20% (5%+ edge vs +400 book = 20% breakeven)
            if p_td >= 0.20:
                edge_class = "STRONG_YES"
                best_market = {"market": "TRIPLE_DOUBLE_YES", "p": round(p_td, 3),
                               "fair_odds": _american(p_td)}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "pace_factor": round(pace_factor, 3),
                "proj_pts": round(proj_pts, 1),
                "proj_reb": round(proj_reb, 1),
                "proj_ast": round(proj_ast, 1),
                "p_pts_10": round(p_pts_10, 3),
                "p_reb_10": round(p_reb_10, 3),
                "p_ast_10": round(p_ast_10, 3),
                "p_td_raw": round(p_td_raw, 4),
                "p_td": round(p_td, 3),
                "fair_yes_odds": _american(p_td),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_td"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "P(TD) = P(>=10 pts) x P(>=10 reb) x P(>=10 ast) x 1.4 correlation_lift. "
                       "STRONG_YES at p>=20% (vs +400 book breakeven).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-td] {o['n_players_projected']} players, {o['n_strong_edges']} strong -> {OUT}")
