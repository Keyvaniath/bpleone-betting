"""
EdgeStat -- NHL skater shots-on-goal (SOG) prop projections.

THE most popular NHL skater prop. Common DK lines: 2.5, 3.5, 4.5 SOG.

Method:
  expected_SOG = season_avg_SOG * pace_factor * opp_shots_allowed_factor
  Poisson at nearest 0.5 line within 0.75 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/nhl_skater_sog_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_sog_props.json")

LEAGUE_SHOTS_PER_GAME = 30.5  # NHL avg team shots on goal per game

# 2024-25 NHL top SOG skaters (SOG per game)
PLAYER_DB = {
    "auston matthews":     {"team": "TOR", "sogg": 4.4},
    "leon draisaitl":      {"team": "EDM", "sogg": 3.8},
    "alex ovechkin":       {"team": "WSH", "sogg": 4.5},
    "nikita kucherov":     {"team": "TBL", "sogg": 3.5},
    "david pastrnak":      {"team": "BOS", "sogg": 4.2},
    "sam reinhart":        {"team": "FLA", "sogg": 3.0},
    "matthew tkachuk":     {"team": "FLA", "sogg": 3.2},
    "connor mcdavid":      {"team": "EDM", "sogg": 3.8},
    "william nylander":    {"team": "TOR", "sogg": 3.5},
    "kirill kaprizov":     {"team": "MIN", "sogg": 3.6},
    "elias pettersson":    {"team": "VAN", "sogg": 3.0},
    "jt miller":           {"team": "VAN", "sogg": 3.2},
    "mikko rantanen":      {"team": "COL", "sogg": 3.8},
    "nathan mackinnon":    {"team": "COL", "sogg": 4.2},
    "sidney crosby":       {"team": "PIT", "sogg": 3.0},
    "evgeni malkin":       {"team": "PIT", "sogg": 2.8},
    "brad marchand":       {"team": "BOS", "sogg": 2.8},
    "elias lindholm":      {"team": "BOS", "sogg": 2.5},
    "tim stutzle":         {"team": "OTT", "sogg": 3.0},
    "brady tkachuk":       {"team": "OTT", "sogg": 3.6},
    "filip forsberg":      {"team": "NSH", "sogg": 3.4},
    "patrik laine":        {"team": "MTL", "sogg": 3.4},
    "jack hughes":         {"team": "NJD", "sogg": 3.5},
    "nico hischier":       {"team": "NJD", "sogg": 2.8},
    "artemi panarin":      {"team": "NYR", "sogg": 3.2},
    "chris kreider":       {"team": "NYR", "sogg": 3.0},
    "mika zibanejad":      {"team": "NYR", "sogg": 3.2},
    "anze kopitar":        {"team": "LAK", "sogg": 2.5},
    "kevin fiala":         {"team": "LAK", "sogg": 2.8},
    "jack eichel":         {"team": "VGK", "sogg": 3.0},
    "mark stone":          {"team": "VGK", "sogg": 2.5},
    "alex debrincat":      {"team": "DET", "sogg": 3.5},
    "dylan larkin":        {"team": "DET", "sogg": 3.0},
    "matt boldy":          {"team": "MIN", "sogg": 3.0},
    "andrei svechnikov":   {"team": "CAR", "sogg": 3.2},
    "sebastian aho":       {"team": "CAR", "sogg": 3.0},
    "tage thompson":       {"team": "BUF", "sogg": 3.6},
    "carter verhaeghe":    {"team": "FLA", "sogg": 2.6},
    "aleksander barkov":   {"team": "FLA", "sogg": 2.6},
    "mitch marner":        {"team": "TOR", "sogg": 2.5},
    "john tavares":        {"team": "TOR", "sogg": 2.8},
    "claude giroux":       {"team": "OTT", "sogg": 2.4},
    "drake batherson":     {"team": "OTT", "sogg": 2.6},
    "roope hintz":         {"team": "DAL", "sogg": 3.0},
    "jason robertson":     {"team": "DAL", "sogg": 3.4},
    "miro heiskanen":      {"team": "DAL", "sogg": 2.6},
    "cale makar":          {"team": "COL", "sogg": 3.5},
    "quinn hughes":        {"team": "VAN", "sogg": 2.4},
    "victor hedman":       {"team": "TBL", "sogg": 2.5},
    "adam fox":            {"team": "NYR", "sogg": 2.0},
}

# Opp team shots-against-allowed per game. League avg ~30.5
TEAM_SHOTS_ALLOWED = {
    "BOS": 28.5, "FLA": 29.0, "TOR": 30.5, "CAR": 27.5, "NYR": 28.0, "NJD": 30.0,
    "DAL": 28.5, "EDM": 30.5, "COL": 28.0, "VGK": 28.5, "WPG": 27.0, "TBL": 30.5,
    "WSH": 31.0, "DET": 33.0, "BUF": 33.5, "MTL": 33.5, "OTT": 31.5, "PIT": 31.0,
    "PHI": 32.0, "NYI": 30.0, "CBJ": 33.0, "VAN": 30.5, "LAK": 28.5, "STL": 31.0,
    "MIN": 30.0, "NSH": 32.0, "ARI": 33.0, "CGY": 30.5, "ANA": 33.5, "SEA": 31.0,
    "SJS": 34.0, "CHI": 33.5,
}

# Pace factor: total combined shot pace of both teams
TEAM_SHOT_PACE = {
    "BOS": 32.0, "FLA": 30.5, "TOR": 31.0, "CAR": 32.0, "NYR": 29.5, "NJD": 30.5,
    "DAL": 30.0, "EDM": 31.5, "COL": 31.0, "VGK": 30.5, "WPG": 28.5, "TBL": 31.5,
    "WSH": 28.5, "DET": 27.5, "BUF": 30.0, "MTL": 28.5, "OTT": 29.0, "PIT": 29.5,
    "PHI": 27.0, "NYI": 27.5, "CBJ": 28.5, "VAN": 30.0, "LAK": 29.0, "STL": 28.5,
    "MIN": 28.5, "NSH": 27.5, "ARI": 26.0, "CGY": 28.5, "ANA": 26.5, "SEA": 28.5,
    "SJS": 26.0, "CHI": 26.5,
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

        home_pace = TEAM_SHOT_PACE.get(home, LEAGUE_SHOTS_PER_GAME)
        away_pace = TEAM_SHOT_PACE.get(away, LEAGUE_SHOTS_PER_GAME)
        home_allowed = TEAM_SHOTS_ALLOWED.get(home, LEAGUE_SHOTS_PER_GAME)
        away_allowed = TEAM_SHOTS_ALLOWED.get(away, LEAGUE_SHOTS_PER_GAME)
        game_pace = (home_pace + away_pace) / 2
        pace_factor = game_pace / LEAGUE_SHOTS_PER_GAME

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_allowed = away_allowed if is_home else home_allowed
            opp_factor = opp_allowed / LEAGUE_SHOTS_PER_GAME

            # Real ESPN shots/game with hardcoded fallback (2026-05-21)
            try:
                from real_stats_lookup import get_player_stat
                stat = get_player_stat("nhl", player_name, "shots_per_game", fallback=info["sogg"], min_games=5)
                base_sogg = stat["value"]
                sogg_source = stat["source"]
            except Exception:
                base_sogg = info["sogg"]
                sogg_source = "fallback"
            projected_sogg = base_sogg * pace_factor * opp_factor

            # Only evaluate nearest 0.5 line within 0.75 of projection
            edge_class = "NONE"
            best_market = None
            base_line = round(projected_sogg * 2) / 2
            for line in (base_line - 0.5, base_line + 0.5):
                if line < 0.5: continue
                if abs(projected_sogg - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, projected_sogg)
                p_under = 1 - p_over
                # STRONG: 10%+ edge vs -120 book (54.5% breakeven), capped at 72%
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"SOG_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"SOG_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp_team": away if is_home else home,
                "season_sogg": round(base_sogg, 2),
                "sogg_source": sogg_source,
                "game_pace": round(game_pace, 1),
                "pace_factor": round(pace_factor, 3),
                "opp_shots_allowed": opp_allowed,
                "opp_factor": round(opp_factor, 3),
                "projected_sogg": round(projected_sogg, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["projected_sogg"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "NHL skater SOG x pace x opp_shots_allowed_factor. Poisson at nearest 0.5 "
                       "line within 0.75 of projection. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-sog] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
