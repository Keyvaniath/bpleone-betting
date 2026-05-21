"""
EdgeStat -- NHL skater POINTS (G+A) prop projections.

Top-3 NHL prop after anytime goal and SOG. Common DK lines: 0.5, 1.5, 2.5 points.

Method:
  expected_pts = season_ppg * pace_factor * opp_goals_allowed_factor
  Poisson at nearest 0.5 line within 0.75 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nhl_skater_points_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_points_props.json")

LEAGUE_GOALS_PER_GAME = 6.2  # NHL avg combined goals per game

# 2024-25 NHL top points-per-game scorers (G+A per game)
PLAYER_DB = {
    "connor mcdavid":      {"team": "EDM", "ppg": 1.65},
    "leon draisaitl":      {"team": "EDM", "ppg": 1.42},
    "nikita kucherov":     {"team": "TBL", "ppg": 1.55},
    "nathan mackinnon":    {"team": "COL", "ppg": 1.50},
    "auston matthews":     {"team": "TOR", "ppg": 1.30},
    "david pastrnak":      {"team": "BOS", "ppg": 1.20},
    "jack hughes":         {"team": "NJD", "ppg": 1.15},
    "mikko rantanen":      {"team": "COL", "ppg": 1.35},
    "kirill kaprizov":     {"team": "MIN", "ppg": 1.30},
    "william nylander":    {"team": "TOR", "ppg": 1.18},
    "matthew tkachuk":     {"team": "FLA", "ppg": 1.10},
    "sam reinhart":        {"team": "FLA", "ppg": 1.05},
    "aleksander barkov":   {"team": "FLA", "ppg": 1.10},
    "alex ovechkin":       {"team": "WSH", "ppg": 0.95},
    "jt miller":           {"team": "VAN", "ppg": 1.05},
    "elias pettersson":    {"team": "VAN", "ppg": 1.00},
    "quinn hughes":        {"team": "VAN", "ppg": 1.00},
    "cale makar":          {"team": "COL", "ppg": 1.20},
    "miro heiskanen":      {"team": "DAL", "ppg": 0.85},
    "jason robertson":     {"team": "DAL", "ppg": 1.00},
    "roope hintz":         {"team": "DAL", "ppg": 0.95},
    "wyatt johnston":      {"team": "DAL", "ppg": 0.85},
    "victor hedman":       {"team": "TBL", "ppg": 0.95},
    "brayden point":       {"team": "TBL", "ppg": 1.10},
    "sidney crosby":       {"team": "PIT", "ppg": 1.05},
    "evgeni malkin":       {"team": "PIT", "ppg": 0.95},
    "erik karlsson":       {"team": "PIT", "ppg": 0.85},
    "brad marchand":       {"team": "BOS", "ppg": 0.90},
    "charlie mcavoy":      {"team": "BOS", "ppg": 0.75},
    "tim stutzle":         {"team": "OTT", "ppg": 0.95},
    "brady tkachuk":       {"team": "OTT", "ppg": 0.85},
    "drake batherson":     {"team": "OTT", "ppg": 0.80},
    "filip forsberg":      {"team": "NSH", "ppg": 0.95},
    "ryan oreilly":        {"team": "NSH", "ppg": 0.80},
    "patrik laine":        {"team": "MTL", "ppg": 0.85},
    "nick suzuki":         {"team": "MTL", "ppg": 0.95},
    "cole caufield":       {"team": "MTL", "ppg": 0.90},
    "lane hutson":         {"team": "MTL", "ppg": 0.85},
    "nico hischier":       {"team": "NJD", "ppg": 0.90},
    "jesper bratt":        {"team": "NJD", "ppg": 1.00},
    "luke hughes":         {"team": "NJD", "ppg": 0.65},
    "artemi panarin":      {"team": "NYR", "ppg": 1.20},
    "mika zibanejad":      {"team": "NYR", "ppg": 0.85},
    "adam fox":            {"team": "NYR", "ppg": 1.00},
    "chris kreider":       {"team": "NYR", "ppg": 0.75},
    "alex debrincat":      {"team": "DET", "ppg": 0.95},
    "dylan larkin":        {"team": "DET", "ppg": 0.95},
    "lucas raymond":       {"team": "DET", "ppg": 0.90},
    "moritz seider":       {"team": "DET", "ppg": 0.60},
    "tage thompson":       {"team": "BUF", "ppg": 0.95},
    "rasmus dahlin":       {"team": "BUF", "ppg": 0.85},
    "anze kopitar":        {"team": "LAK", "ppg": 0.80},
    "kevin fiala":         {"team": "LAK", "ppg": 0.85},
    "adrian kempe":        {"team": "LAK", "ppg": 0.95},
    "jack eichel":         {"team": "VGK", "ppg": 1.10},
    "mark stone":          {"team": "VGK", "ppg": 0.85},
    "jonathan marchessault": {"team": "NSH", "ppg": 0.80},
    "sebastian aho":       {"team": "CAR", "ppg": 0.95},
    "andrei svechnikov":   {"team": "CAR", "ppg": 0.80},
    "mitch marner":        {"team": "TOR", "ppg": 1.15},
    "john tavares":        {"team": "TOR", "ppg": 0.95},
    "morgan rielly":       {"team": "TOR", "ppg": 0.70},
    "elias lindholm":      {"team": "BOS", "ppg": 0.65},
    "claude giroux":       {"team": "OTT", "ppg": 0.75},
    "matt boldy":          {"team": "MIN", "ppg": 0.90},
    "joel eriksson ek":    {"team": "MIN", "ppg": 0.80},
}

# Per-team goals allowed per game (proxy for "scoring against" defense). League avg ~3.1
TEAM_GA_PER_GAME = {
    "BOS": 2.7, "FLA": 2.6, "DAL": 2.7, "CAR": 2.5, "EDM": 2.9, "COL": 2.8, "WPG": 2.5,
    "TBL": 2.9, "NYR": 2.8, "TOR": 2.95, "VGK": 2.9, "NJD": 2.95, "WSH": 3.0, "VAN": 3.05,
    "LAK": 2.7, "STL": 3.05, "MIN": 3.0, "NSH": 3.1, "OTT": 3.15, "PHI": 3.2, "MTL": 3.4,
    "BUF": 3.45, "PIT": 3.2, "DET": 3.4, "ARI": 3.45, "CGY": 3.15, "ANA": 3.55, "SEA": 3.2,
    "SJS": 3.7, "CHI": 3.55, "CBJ": 3.55, "NYI": 3.05,
}

TEAM_PACE = {  # combined goals/game pace
    "BOS": 6.4, "FLA": 6.3, "DAL": 6.3, "CAR": 6.4, "EDM": 6.6, "COL": 6.5, "WPG": 6.2,
    "TBL": 6.5, "NYR": 6.2, "TOR": 6.3, "VGK": 6.4, "NJD": 6.5, "WSH": 6.0, "VAN": 6.2,
    "LAK": 5.9, "STL": 6.1, "MIN": 6.0, "NSH": 6.1, "OTT": 6.3, "PHI": 6.1, "MTL": 6.4,
    "BUF": 6.5, "PIT": 6.2, "DET": 6.2, "ARI": 5.9, "CGY": 5.9, "ANA": 6.1, "SEA": 6.0,
    "SJS": 6.3, "CHI": 6.0, "CBJ": 6.2, "NYI": 6.0,
}


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
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue

        home_pace = TEAM_PACE.get(home, LEAGUE_GOALS_PER_GAME)
        away_pace = TEAM_PACE.get(away, LEAGUE_GOALS_PER_GAME)
        home_ga = TEAM_GA_PER_GAME.get(home, 3.1)
        away_ga = TEAM_GA_PER_GAME.get(away, 3.1)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_GOALS_PER_GAME

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_ga = away_ga if is_home else home_ga
            # Higher opp_ga -> opponent allows more goals -> more points opportunity
            opp_factor = opp_ga / 3.1

            base_ppg = info["ppg"]
            projected_pts = base_ppg * pace_factor * opp_factor

            # Only evaluate nearest 0.5 line within 0.75 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_pts * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected_pts - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, projected_pts)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"PTS_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"PTS_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_ppg": base_ppg,
                "game_pace": round(game_pace, 2),
                "pace_factor": round(pace_factor, 3),
                "opp_ga_per_game": opp_ga,
                "opp_factor": round(opp_factor, 3),
                "projected_pts": round(projected_pts, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_pts"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NHL skater PTS (G+A) x pace x opp_goals_allowed_factor. Poisson at nearest "
                       "0.5 line within 0.75 of projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-pts] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
