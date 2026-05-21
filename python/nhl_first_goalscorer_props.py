"""
EdgeStat -- NHL first-goalscorer (FGS) prop projections.

High-juice prop (typical book +800 to +2500 per player). Common DK market:
"First goal scorer of the game - [Player Name]".

Method:
  Each game has total expected goals ~6.0-6.5.
  P(team_X scores first) approximated by team_xG / total_xG.
  P(player_Y is first scorer | team_X scores first) = player_xG / team_xG
  -> P(player_Y is first goalscorer) = player_gpg / total_game_goals

  Simplification: P(player is FGS) ~ player_gpg / sum(all_players_gpg in match)

  STRONG_YES when P(player is FGS) >= 8% (vs typical +1100 book = 8.3%).

Output: data/nhl_first_goalscorer_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_first_goalscorer_props.json")

# 2024-25 NHL top GPG (goals per game) shooters
PLAYER_DB = {
    "auston matthews":     {"team": "TOR", "gpg": 0.70},
    "leon draisaitl":      {"team": "EDM", "gpg": 0.65},
    "alex ovechkin":       {"team": "WSH", "gpg": 0.62},
    "nikita kucherov":     {"team": "TBL", "gpg": 0.55},
    "david pastrnak":      {"team": "BOS", "gpg": 0.58},
    "sam reinhart":        {"team": "FLA", "gpg": 0.55},
    "matthew tkachuk":     {"team": "FLA", "gpg": 0.42},
    "connor mcdavid":      {"team": "EDM", "gpg": 0.55},
    "william nylander":    {"team": "TOR", "gpg": 0.52},
    "kirill kaprizov":     {"team": "MIN", "gpg": 0.55},
    "mikko rantanen":      {"team": "COL", "gpg": 0.55},
    "nathan mackinnon":    {"team": "COL", "gpg": 0.55},
    "brad marchand":       {"team": "BOS", "gpg": 0.42},
    "tage thompson":       {"team": "BUF", "gpg": 0.50},
    "alex debrincat":      {"team": "DET", "gpg": 0.50},
    "patrik laine":        {"team": "MTL", "gpg": 0.42},
    "jack hughes":         {"team": "NJD", "gpg": 0.50},
    "artemi panarin":      {"team": "NYR", "gpg": 0.42},
    "chris kreider":       {"team": "NYR", "gpg": 0.45},
    "mika zibanejad":      {"team": "NYR", "gpg": 0.42},
    "jack eichel":         {"team": "VGK", "gpg": 0.42},
    "brady tkachuk":       {"team": "OTT", "gpg": 0.45},
    "tim stutzle":         {"team": "OTT", "gpg": 0.40},
    "filip forsberg":      {"team": "NSH", "gpg": 0.45},
    "nico hischier":       {"team": "NJD", "gpg": 0.42},
    "jason robertson":     {"team": "DAL", "gpg": 0.42},
    "roope hintz":         {"team": "DAL", "gpg": 0.40},
    "matt boldy":          {"team": "MIN", "gpg": 0.42},
    "carter verhaeghe":    {"team": "FLA", "gpg": 0.40},
    "aleksander barkov":   {"team": "FLA", "gpg": 0.40},
    "elias pettersson":    {"team": "VAN", "gpg": 0.42},
    "jt miller":           {"team": "VAN", "gpg": 0.40},
    "sebastian aho":       {"team": "CAR", "gpg": 0.42},
    "andrei svechnikov":   {"team": "CAR", "gpg": 0.40},
    "dylan larkin":        {"team": "DET", "gpg": 0.40},
    "anze kopitar":        {"team": "LAK", "gpg": 0.32},
    "kevin fiala":         {"team": "LAK", "gpg": 0.38},
    "adrian kempe":        {"team": "LAK", "gpg": 0.42},
    "brayden point":       {"team": "TBL", "gpg": 0.50},
    "victor hedman":       {"team": "TBL", "gpg": 0.20},
    "sidney crosby":       {"team": "PIT", "gpg": 0.40},
    "evgeni malkin":       {"team": "PIT", "gpg": 0.38},
    "mitch marner":        {"team": "TOR", "gpg": 0.32},
    "john tavares":        {"team": "TOR", "gpg": 0.38},
    "cole caufield":       {"team": "MTL", "gpg": 0.42},
    "nick suzuki":         {"team": "MTL", "gpg": 0.38},
    "elias lindholm":      {"team": "BOS", "gpg": 0.30},
}

LEAGUE_GAME_GOALS = 6.2  # combined goals per game


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


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

        # Find candidate players in this game
        game_players = [(name, info) for name, info in PLAYER_DB.items()
                        if info["team"] in (home, away)]
        if not game_players: continue

        # Resolve each player's GPG via real ESPN stats with hardcoded fallback
        try:
            from real_stats_lookup import get_player_stat
            _have_real = True
        except Exception:
            _have_real = False

        per_player_gpg = {}
        for name, info in game_players:
            if _have_real:
                s = get_player_stat("nhl", name, "goals_per_game", fallback=info["gpg"], min_games=5)
                per_player_gpg[name] = (s["value"], s["source"])
            else:
                per_player_gpg[name] = (info["gpg"], "fallback")

        total_player_gpg = sum(v[0] for v in per_player_gpg.values())
        # Add bench/depth contribution ~ 0.5 GPG per team (4 depth lines combined)
        depth_gpg = 1.0
        total_gpg_match = total_player_gpg + depth_gpg

        # P(any goal happens in regulation) ~ 1 - P(0-0 tie)
        # Assume Poisson goals with mean LEAGUE_GAME_GOALS for whole game
        p_any_goal = 1 - math.exp(-LEAGUE_GAME_GOALS)

        for player_name, info in game_players:
            is_home = info["team"] == home
            opp = away if is_home else home
            real_gpg, gpg_source = per_player_gpg[player_name]
            # P(player is first to score) = (player_gpg / total_match_gpg) * P(any goal)
            p_fgs = (real_gpg / total_gpg_match) * p_any_goal

            edge_class = "NONE"
            best_market = None
            # STRONG_YES when our P(FGS) >= 8% (vs ~+1100 book = 8.3%)
            if p_fgs >= 0.08:
                edge_class = "STRONG_YES"
                best_market = {"market": "FIRST_GOAL_SCORER_YES", "p": round(p_fgs, 3),
                               "fair_odds": _american(p_fgs)}

            rows.append({
                "matchup": f"{away} @ {home}",
                "player": player_name,
                "team": info["team"],
                "opp": opp,
                "season_gpg": round(real_gpg, 3),
                "gpg_source": gpg_source,
                "total_match_gpg": round(total_gpg_match, 2),
                "p_fgs": round(p_fgs, 3),
                "fair_yes_odds": _american(p_fgs),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_fgs"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "P(FGS) = (player_gpg / total_match_gpg) * P(any_goal_in_game). "
                       "Includes 1.0 depth_gpg per game for non-DB players. "
                       "STRONG_YES when P(FGS) >= 8% (vs +1100 book).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-fgs] {o['n_players']} players, {o['n_strong_edges']} strong edges -> {OUT}")
